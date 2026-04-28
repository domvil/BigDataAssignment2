from __future__ import annotations

import logging
from datetime import timezone

import discord
from discord.ext import commands

from .binance_stream import BinancePriceStream
from .config import AppConfig
from .models import PriceSnapshot, WatchSettings
from .service import PriceWatcherService
from .settings_store import SettingsStore

LOGGER = logging.getLogger(__name__)


def _format_price(value: float | None) -> str:
    if value is None:
        return "disabled"
    return f"${value:,.2f}"


def _format_snapshot(snapshot: PriceSnapshot | None) -> str:
    if snapshot is None:
        return "No market price has been received yet."
    timestamp = snapshot.observed_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"{_format_price(snapshot.price)} at {timestamp}"


def _format_settings(settings: WatchSettings, running: bool, snapshot: PriceSnapshot | None) -> str:
    channel_value = (
        f"<#{settings.notification_channel_id}>"
        if settings.notification_channel_id is not None
        else "not set"
    )
    return "\n".join(
        [
            f"Watcher state: {'running' if running else 'stopped'}",
            f"Latest BTC price: {_format_snapshot(snapshot)}",
            f"Percent alert: {settings.percent_threshold:.2f}%" if settings.percent_threshold is not None else "Percent alert: disabled",
            f"Upper price alert: {_format_price(settings.upper_price)}",
            f"Lower price alert: {_format_price(settings.lower_price)}",
            f"Cooldown: {settings.cooldown_seconds} seconds",
            f"Notification channel: {channel_value}",
        ]
    )


class WatchCommands(commands.Cog):
    def __init__(self, bot: "PriceWatcherBot") -> None:
        self.bot = bot

    @commands.group(name="watch", invoke_without_command=True)
    async def watch(self, ctx: commands.Context["PriceWatcherBot"]) -> None:
        await ctx.send(self._help_text())

    @watch.command(name="help")
    async def help_command(self, ctx: commands.Context["PriceWatcherBot"]) -> None:
        await ctx.send(self._help_text())

    @watch.command(name="start")
    async def start(self, ctx: commands.Context["PriceWatcherBot"]) -> None:
        settings, _, _ = await self.bot.service.get_state()
        configured_channel_id = settings.notification_channel_id
        if settings.notification_channel_id is None:
            updated_settings = await self.bot.service.set_notification_channel(ctx.channel.id)
            configured_channel_id = updated_settings.notification_channel_id

        started = await self.bot.service.start()
        if started:
            channel_text = (
                f"<#{configured_channel_id}>"
                if configured_channel_id is not None
                else "the configured channel"
            )
            await ctx.send(f"Price watcher started. Alerts will be posted in {channel_text}.")
            return

        await ctx.send("Price watcher is already running.")

    @watch.command(name="stop")
    async def stop(self, ctx: commands.Context["PriceWatcherBot"]) -> None:
        stopped = await self.bot.service.stop()
        if stopped:
            await ctx.send("Price watcher stopped.")
            return

        await ctx.send("Price watcher is already stopped.")

    @watch.command(name="status")
    async def status(self, ctx: commands.Context["PriceWatcherBot"]) -> None:
        settings, snapshot, running = await self.bot.service.get_state()
        await ctx.send(_format_settings(settings, running, snapshot))

    @watch.command(name="price")
    async def price(self, ctx: commands.Context["PriceWatcherBot"]) -> None:
        _, snapshot, _ = await self.bot.service.get_state()
        await ctx.send(f"Latest BTC price: {_format_snapshot(snapshot)}")

    @watch.command(name="percent")
    async def percent(self, ctx: commands.Context["PriceWatcherBot"], value: str) -> None:
        threshold = self._parse_optional_float(value, "percent threshold")
        settings = await self.bot.service.set_percent_threshold(threshold)
        if settings.percent_threshold is None:
            await ctx.send("Percent-change alerts disabled.")
            return

        await ctx.send(f"Percent-change alerts now fire at {settings.percent_threshold:.2f}%.")

    @watch.command(name="above")
    async def above(self, ctx: commands.Context["PriceWatcherBot"], value: str) -> None:
        threshold = self._parse_optional_float(value, "upper price")
        settings = await self.bot.service.set_upper_price(threshold)
        if settings.upper_price is None:
            await ctx.send("Upper-price alerts disabled.")
            return

        await ctx.send(f"Upper-price alerts now fire above {_format_price(settings.upper_price)}.")

    @watch.command(name="below")
    async def below(self, ctx: commands.Context["PriceWatcherBot"], value: str) -> None:
        threshold = self._parse_optional_float(value, "lower price")
        settings = await self.bot.service.set_lower_price(threshold)
        if settings.lower_price is None:
            await ctx.send("Lower-price alerts disabled.")
            return

        await ctx.send(f"Lower-price alerts now fire below {_format_price(settings.lower_price)}.")

    @watch.command(name="cooldown")
    async def cooldown(self, ctx: commands.Context["PriceWatcherBot"], seconds: int) -> None:
        if seconds < 0:
            raise commands.BadArgument("Cooldown must be 0 or greater.")
        settings = await self.bot.service.set_cooldown_seconds(seconds)
        await ctx.send(f"Cooldown updated to {settings.cooldown_seconds} seconds.")

    @watch.command(name="channel")
    async def channel(
        self,
        ctx: commands.Context["PriceWatcherBot"],
        channel: discord.TextChannel | None = None,
    ) -> None:
        target_channel = channel or ctx.channel
        await self.bot.service.set_notification_channel(target_channel.id)
        await ctx.send(f"Notifications will be posted in {target_channel.mention}.")

    def _help_text(self) -> str:
        prefix = self.bot.command_prefix
        return "\n".join(
            [
                "BTC watcher commands:",
                f"{prefix}watch start - start the Binance listener",
                f"{prefix}watch stop - stop the Binance listener",
                f"{prefix}watch status - show current settings and latest price",
                f"{prefix}watch price - show the latest BTC price seen",
                f"{prefix}watch percent <value|off> - set percent alert threshold",
                f"{prefix}watch above <value|off> - alert when BTC crosses above a price",
                f"{prefix}watch below <value|off> - alert when BTC crosses below a price",
                f"{prefix}watch cooldown <seconds> - limit repeated alerts",
                f"{prefix}watch channel [#channel] - choose the notification channel",
            ]
        )

    @staticmethod
    def _parse_optional_float(value: str, field_name: str) -> float | None:
        lowered = value.lower()
        if lowered in {"off", "none", "disable"}:
            return None

        parsed = float(value)
        if parsed <= 0:
            raise commands.BadArgument(f"{field_name} must be greater than 0.")
        return parsed


class PriceWatcherBot(commands.Bot):
    def __init__(self, config: AppConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix=config.command_prefix, intents=intents)
        self.config = config
        self.service = PriceWatcherService(
            stream=BinancePriceStream(config.stream_url),
            settings_store=SettingsStore(config.settings_path),
            send_notification=self.send_notification,
            startup_settings=config.startup_settings,
        )
        self._auto_started = False

    async def setup_hook(self) -> None:
        await self.add_cog(WatchCommands(self))

    async def on_ready(self) -> None:
        LOGGER.info("Logged in as %s", self.user)
        if self.config.auto_start_on_ready and not self._auto_started:
            self._auto_started = True
            await self.service.start()

    async def close(self) -> None:
        await self.service.stop()
        await super().close()

    async def send_notification(self, message: str, channel_id: int | None) -> None:
        if channel_id is None:
            LOGGER.info("Notification skipped because no Discord channel is configured.")
            return

        channel = self.get_channel(channel_id)
        if channel is None:
            channel = await self.fetch_channel(channel_id)

        send_method = getattr(channel, "send", None)
        if send_method is None:
            LOGGER.warning("Configured channel %s does not support sending messages.", channel_id)
            return

        await send_method(message)

    async def on_command_error(
        self,
        context: commands.Context["PriceWatcherBot"],
        exception: commands.CommandError,
    ) -> None:
        if isinstance(exception, commands.CommandNotFound):
            return

        if isinstance(exception, (commands.BadArgument, commands.MissingRequiredArgument)):
            await context.send(f"Invalid command input: {exception}")
            return

        LOGGER.exception("Unhandled command error: %s", exception)
        await context.send("The command failed. Check the container logs for details.")

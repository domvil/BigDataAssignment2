from __future__ import annotations

import argparse
import asyncio
import logging

from discord.errors import LoginFailure

from .config import AppConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discord-controlled Binance BTC price watcher."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Load configuration and print the resolved settings without starting the bot.",
    )
    return parser


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


async def async_main(check_only: bool) -> int:
    config = AppConfig.from_env()
    if check_only:
        print("Configuration loaded successfully.")
        print(f"Command prefix: {config.command_prefix}")
        print(f"Binance stream: {config.stream_url}")
        print(f"Settings file: {config.settings_path}")
        print(f"Discord token configured: {'yes' if config.discord_token else 'no'}")
        return 0

    if not config.discord_token:
        raise RuntimeError("DISCORD_TOKEN is required to start the Discord bot.")

    from .bot import PriceWatcherBot

    bot = PriceWatcherBot(config)
    async with bot:
        await bot.start(config.discord_token)
    return 0


def main() -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(async_main(args.check))
    except KeyboardInterrupt:
        return 0
    except LoginFailure:
        logging.getLogger(__name__).error(
            "Discord login failed: DISCORD_TOKEN is invalid or expired."
        )
        return 1
    except (RuntimeError, ValueError) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1
    except Exception:
        logging.getLogger(__name__).exception("Application exited with an error.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

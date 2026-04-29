from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from .alert_engine import AlertEngine
from .binance_stream import BinancePriceStream
from .models import PriceSnapshot, WatchSettings
from .settings_store import SettingsStore

LOGGER = logging.getLogger(__name__)


class PriceWatcherService:
    def __init__(
        self,
        stream: BinancePriceStream,
        settings_store: SettingsStore,
        send_notification: Callable[[str, int | None], Awaitable[None]],
        startup_settings: WatchSettings,
    ) -> None:
        self._stream = stream
        self._settings_store = settings_store
        self._send_notification = send_notification
        self._settings = settings_store.load(startup_settings)
        self._last_snapshot: PriceSnapshot | None = None
        self._engine = AlertEngine()
        self._task: asyncio.Task[None] | None = None
        # The lock keeps settings changes and price updates from stepping on each other.
        self._state_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> bool:
        async with self._state_lock:
            if self.is_running:
                LOGGER.info("Price watcher start requested, but the watcher is already running.")
                return False

            # Start percent tracking from the most recent known price.
            self._engine.reset(self._last_snapshot.price if self._last_snapshot else None)
            LOGGER.info(
                "Starting price watcher with percent=%s upper=%s lower=%s cooldown=%ss channel=%s",
                self._settings.percent_threshold,
                self._settings.upper_price,
                self._settings.lower_price,
                self._settings.cooldown_seconds,
                self._settings.notification_channel_id,
            )
            self._task = asyncio.create_task(self._run_stream(), name="binance-price-watcher")
            self._task.add_done_callback(self._on_stream_done)
            return True

    async def stop(self) -> bool:
        async with self._state_lock:
            task = self._task
            self._task = None

        if task is None:
            LOGGER.info("Price watcher stop requested, but the watcher is already stopped.")
            return False

        LOGGER.info("Stopping price watcher.")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        async with self._state_lock:
            self._engine.reset(self._last_snapshot.price if self._last_snapshot else None)
        return True

    async def set_percent_threshold(self, value: float | None) -> WatchSettings:
        async with self._state_lock:
            self._settings.percent_threshold = value
            self._engine.reanchor_percent_reference(
                self._last_snapshot.price if self._last_snapshot else None
            )
            self._persist_settings()
            return self._copy_settings()

    async def set_upper_price(self, value: float | None) -> WatchSettings:
        async with self._state_lock:
            self._settings.upper_price = value
            self._persist_settings()
            return self._copy_settings()

    async def set_lower_price(self, value: float | None) -> WatchSettings:
        async with self._state_lock:
            self._settings.lower_price = value
            self._persist_settings()
            return self._copy_settings()

    async def set_cooldown_seconds(self, value: int) -> WatchSettings:
        async with self._state_lock:
            self._settings.cooldown_seconds = value
            self._persist_settings()
            return self._copy_settings()

    async def set_notification_channel(self, channel_id: int | None) -> WatchSettings:
        async with self._state_lock:
            self._settings.notification_channel_id = channel_id
            self._persist_settings()
            return self._copy_settings()

    async def get_state(self) -> tuple[WatchSettings, PriceSnapshot | None, bool]:
        async with self._state_lock:
            return self._copy_settings(), self._copy_snapshot(), self.is_running

    async def _run_stream(self) -> None:
        async for snapshot in self._stream.listen():
            async with self._state_lock:
                self._last_snapshot = snapshot
                # Use a copy so notification sending happens outside the lock.
                settings = self._copy_settings()
                events = self._engine.evaluate(snapshot.price, settings, snapshot.observed_at)
                channel_id = settings.notification_channel_id

            for event in events:
                LOGGER.info("Alert triggered: %s", event.message)
                try:
                    await self._send_notification(event.message, channel_id)
                except Exception as exc:
                    LOGGER.warning("Failed to deliver notification: %s", exc)

    def _persist_settings(self) -> None:
        self._settings_store.save(self._settings)

    def _copy_settings(self) -> WatchSettings:
        return WatchSettings(
            percent_threshold=self._settings.percent_threshold,
            upper_price=self._settings.upper_price,
            lower_price=self._settings.lower_price,
            cooldown_seconds=self._settings.cooldown_seconds,
            notification_channel_id=self._settings.notification_channel_id,
        )

    def _copy_snapshot(self) -> PriceSnapshot | None:
        if self._last_snapshot is None:
            return None

        return PriceSnapshot(
            price=self._last_snapshot.price,
            observed_at=self._last_snapshot.observed_at,
        )

    def _on_stream_done(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return

        try:
            task.result()
        except Exception as exc:
            LOGGER.exception("Price watcher stopped unexpectedly: %s", exc)

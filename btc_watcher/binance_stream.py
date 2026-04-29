from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

import websockets

from .models import PriceSnapshot

LOGGER = logging.getLogger(__name__)


class BinancePriceStream:
    def __init__(
        self,
        url: str,
        reconnect_delay: float = 5.0,
        message_log_interval: float = 15.0,
    ) -> None:
        self._url = url
        self._reconnect_delay = reconnect_delay
        self._message_log_interval = message_log_interval
        self._message_count = 0
        self._last_message_log_at = 0.0

    async def listen(self) -> AsyncIterator[PriceSnapshot]:
        while True:
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as websocket:
                    self._last_message_log_at = 0.0
                    LOGGER.info("Connected to Binance stream: %s", self._url)
                    async for message in websocket:
                        self._message_count += 1
                        payload = json.loads(message)
                        price = self._extract_price(payload)
                        self._maybe_log_message(payload, price)
                        if price is None:
                            continue
                        yield PriceSnapshot.now(price)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning(
                    "Binance stream disconnected: %s. Reconnecting in %.1f seconds.",
                    exc,
                    self._reconnect_delay,
                )
                await asyncio.sleep(self._reconnect_delay)

    def _maybe_log_message(self, payload: dict[str, object], price: float | None) -> None:
        now = time.monotonic()
        if self._message_count != 1 and now - self._last_message_log_at < self._message_log_interval:
            return

        self._last_message_log_at = now
        if price is None:
            LOGGER.info(
                "Binance message #%s did not include a usable price. Payload: %s",
                self._message_count,
                self._format_payload(payload),
            )
            return

        LOGGER.info(
            "Binance message #%s received. Latest BTC price: $%s. Payload: %s",
            self._message_count,
            f"{price:,.2f}",
            self._format_payload(payload),
        )

    @staticmethod
    def _format_payload(payload: dict[str, object]) -> str:
        rendered = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        if len(rendered) > 200:
            return f"{rendered[:197]}..."
        return rendered

    @staticmethod
    def _extract_price(payload: dict[str, object]) -> float | None:
        for field in ("c", "p"):
            raw_value = payload.get(field)
            if raw_value is None:
                continue
            try:
                return float(raw_value)
            except (TypeError, ValueError):
                return None
        return None

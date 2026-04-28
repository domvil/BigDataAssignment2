from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import websockets

from .models import PriceSnapshot

LOGGER = logging.getLogger(__name__)


class BinancePriceStream:
    def __init__(self, url: str, reconnect_delay: float = 5.0) -> None:
        self._url = url
        self._reconnect_delay = reconnect_delay

    async def listen(self) -> AsyncIterator[PriceSnapshot]:
        while True:
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=20,
                    ping_timeout=20,
                ) as websocket:
                    LOGGER.info("Connected to Binance stream: %s", self._url)
                    async for message in websocket:
                        payload = json.loads(message)
                        price = self._extract_price(payload)
                        if price is None:
                            continue
                        yield PriceSnapshot.now(price)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                LOGGER.warning("Binance stream disconnected: %s", exc)
                await asyncio.sleep(self._reconnect_delay)

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

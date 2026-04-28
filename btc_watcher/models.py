from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def _parse_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


@dataclass
class WatchSettings:
    # These values control which BTC alerts are active.
    percent_threshold: float | None = 1.0
    upper_price: float | None = None
    lower_price: float | None = None
    cooldown_seconds: int = 60
    notification_channel_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WatchSettings":
        return cls(
            percent_threshold=_parse_optional_float(raw.get("percent_threshold")),
            upper_price=_parse_optional_float(raw.get("upper_price")),
            lower_price=_parse_optional_float(raw.get("lower_price")),
            cooldown_seconds=int(raw.get("cooldown_seconds", 60)),
            notification_channel_id=(
                int(raw["notification_channel_id"])
                if raw.get("notification_channel_id") is not None
                else None
            ),
        )


@dataclass
class PriceSnapshot:
    # One BTC price update from Binance.
    price: float
    observed_at: datetime

    @classmethod
    def now(cls, price: float) -> "PriceSnapshot":
        return cls(price=price, observed_at=datetime.now(timezone.utc))


@dataclass
class AlertEvent:
    # Message prepared for Discord after a rule is triggered.
    key: str
    message: str
    occurred_at: datetime

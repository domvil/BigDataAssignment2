from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .models import WatchSettings


def _optional_float(name: str) -> float | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None
    value = float(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


def _optional_int(name: str) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None
    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return value


@dataclass(slots=True)
class AppConfig:
    discord_token: str | None
    command_prefix: str
    stream_url: str
    settings_path: Path
    startup_settings: WatchSettings
    auto_start_on_ready: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        cooldown_seconds = int(os.getenv("DEFAULT_COOLDOWN_SECONDS", "60"))
        if cooldown_seconds < 0:
            raise ValueError("DEFAULT_COOLDOWN_SECONDS must be 0 or greater.")

        return cls(
            discord_token=os.getenv("DISCORD_TOKEN"),
            command_prefix=os.getenv("DISCORD_COMMAND_PREFIX", "!"),
            stream_url=os.getenv(
                "BINANCE_STREAM_URL",
                "wss://stream.binance.com:9443/ws/btcusdt@ticker",
            ),
            settings_path=Path(os.getenv("SETTINGS_FILE", "data/settings.json")),
            startup_settings=WatchSettings(
                percent_threshold=_optional_float("DEFAULT_PERCENT_THRESHOLD") or 1.0,
                upper_price=_optional_float("DEFAULT_UPPER_PRICE"),
                lower_price=_optional_float("DEFAULT_LOWER_PRICE"),
                cooldown_seconds=cooldown_seconds,
                notification_channel_id=_optional_int("DISCORD_NOTIFICATION_CHANNEL_ID"),
            ),
            auto_start_on_ready=os.getenv("AUTO_START_ON_READY", "false").lower()
            in {"1", "true", "yes", "on"},
        )

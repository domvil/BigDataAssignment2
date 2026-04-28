from __future__ import annotations

import json
from pathlib import Path

from .models import WatchSettings


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self, defaults: WatchSettings) -> WatchSettings:
        if not self._path.exists():
            return WatchSettings.from_dict(defaults.to_dict())

        with self._path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        merged = defaults.to_dict()
        merged.update(raw)
        return WatchSettings.from_dict(merged)

    def save(self, settings: WatchSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(settings.to_dict(), handle, indent=2, sort_keys=True)

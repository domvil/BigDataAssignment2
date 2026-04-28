from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import AlertEvent, WatchSettings


def _format_price(value: float) -> str:
    return f"${value:,.2f}"


class AlertEngine:
    def __init__(self) -> None:
        self._previous_price: float | None = None
        self._reference_price: float | None = None
        self._last_notification_at: dict[str, datetime] = {}

    def reset(self, current_price: float | None = None) -> None:
        self._previous_price = current_price
        self._reference_price = current_price
        self._last_notification_at.clear()

    def reanchor_percent_reference(self, current_price: float | None) -> None:
        self._reference_price = current_price

    def evaluate(
        self,
        price: float,
        settings: WatchSettings,
        observed_at: datetime | None = None,
    ) -> list[AlertEvent]:
        now = observed_at or datetime.now(timezone.utc)
        events: list[AlertEvent] = []

        if self._reference_price is None:
            self._reference_price = price

        if settings.percent_threshold is not None and self._reference_price is not None:
            change_percent = ((price - self._reference_price) / self._reference_price) * 100
            if abs(change_percent) >= settings.percent_threshold:
                key = "percent"
                if self._is_outside_cooldown(key, now, settings.cooldown_seconds):
                    direction = "up" if change_percent > 0 else "down"
                    events.append(
                        AlertEvent(
                            key=key,
                            message=(
                                f"BTC moved {direction} {abs(change_percent):.2f}% to "
                                f"{_format_price(price)} (reference {_format_price(self._reference_price)})."
                            ),
                            occurred_at=now,
                        )
                    )
                    self._mark_notification(key, now)
                    self._reference_price = price

        if self._previous_price is not None:
            if (
                settings.upper_price is not None
                and self._previous_price < settings.upper_price <= price
            ):
                key = f"above:{settings.upper_price:.2f}"
                if self._is_outside_cooldown(key, now, settings.cooldown_seconds):
                    events.append(
                        AlertEvent(
                            key=key,
                            message=(
                                f"BTC crossed above {_format_price(settings.upper_price)} and is now "
                                f"{_format_price(price)}."
                            ),
                            occurred_at=now,
                        )
                    )
                    self._mark_notification(key, now)

            if (
                settings.lower_price is not None
                and self._previous_price > settings.lower_price >= price
            ):
                key = f"below:{settings.lower_price:.2f}"
                if self._is_outside_cooldown(key, now, settings.cooldown_seconds):
                    events.append(
                        AlertEvent(
                            key=key,
                            message=(
                                f"BTC crossed below {_format_price(settings.lower_price)} and is now "
                                f"{_format_price(price)}."
                            ),
                            occurred_at=now,
                        )
                    )
                    self._mark_notification(key, now)

        self._previous_price = price
        return events

    def _is_outside_cooldown(self, key: str, now: datetime, cooldown_seconds: int) -> bool:
        if cooldown_seconds <= 0:
            return True

        last_sent_at = self._last_notification_at.get(key)
        if last_sent_at is None:
            return True

        return now - last_sent_at >= timedelta(seconds=cooldown_seconds)

    def _mark_notification(self, key: str, now: datetime) -> None:
        self._last_notification_at[key] = now

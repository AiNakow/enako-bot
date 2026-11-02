"""Immutable public input and output models."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class Visit:
    entered_at: datetime
    exited_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EarlyBirdConfig:
    start: time
    end: time
    cap_fen: int


@dataclass(frozen=True, slots=True, kw_only=True)
class BillingConfig:
    day_start: time
    night_start: time
    hourly_rate_fen: int
    day_cap_fen: int
    night_cap_fen: int
    first_hour_free_seconds: int
    step_seconds: int
    early_bird: EarlyBirdConfig | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DailyPresenceSeconds:
    early_bird: Decimal
    day: Decimal
    night: Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class BillResult:
    stat_date: date
    daily_presence_seconds: DailyPresenceSeconds
    current_presence_seconds: Decimal
    current_payable_fen: int

    def to_json(self) -> str:
        from .serialization import serialize_result

        return serialize_result(self)

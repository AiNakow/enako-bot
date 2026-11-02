"""One ordered validation boundary and an exact integer time axis."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from .errors import BillingConfigError, BillingInputError
from .models import BillingConfig, EarlyBirdConfig, Visit

BEIJING = timezone(timedelta(hours=8))
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MIN_DATE = date(2, 1, 1)
MAX_DATE = date(9998, 12, 31)
MAX_INT = 2**63 - 1


@dataclass(frozen=True, slots=True, kw_only=True)
class _ValidatedVisit:
    original_index: int
    entered_us: int
    exited_us: int | None
    end_us: int


def datetime_to_us(value: datetime) -> int:
    delta = value - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def us_to_beijing(value: int) -> datetime:
    return (EPOCH + timedelta(microseconds=value)).astimezone(BEIJING)


def _local_time(value: object, field: str) -> None:
    if type(value) is not time:
        raise BillingConfigError(code="INVALID_TYPE", field=field)
    if value.tzinfo is not None or value.fold != 0:
        raise BillingConfigError(code="INVALID_LOCAL_TIME", field=field)


def _integer(value: object, minimum: int, maximum: int, field: str) -> None:
    if type(value) is not int:
        raise BillingConfigError(code="INVALID_TYPE", field=field)
    if not minimum <= value <= maximum:
        raise BillingConfigError(code="OUT_OF_RANGE", field=field)


def _config(config: object) -> None:
    if type(config) is not BillingConfig:
        raise BillingConfigError(code="INVALID_TYPE", field="config")
    _local_time(config.day_start, "config.day_start")
    _local_time(config.night_start, "config.night_start")
    for field in ("hourly_rate_fen", "day_cap_fen", "night_cap_fen"):
        _integer(getattr(config, field), 1, MAX_INT, f"config.{field}")
    _integer(config.first_hour_free_seconds, 0, 3599, "config.first_hour_free_seconds")
    _integer(config.step_seconds, 1, MAX_INT, "config.step_seconds")
    early = config.early_bird
    if early is not None:
        if type(early) is not EarlyBirdConfig:
            raise BillingConfigError(code="INVALID_TYPE", field="config.early_bird")
        _local_time(early.start, "config.early_bird.start")
        _local_time(early.end, "config.early_bird.end")
        _integer(early.cap_fen, 1, MAX_INT, "config.early_bird.cap_fen")
    if config.day_start >= config.night_start:
        raise BillingConfigError(code="INVALID_WINDOW", field="config.night_start")
    if early is not None and early.start >= early.end:
        raise BillingConfigError(code="INVALID_WINDOW", field="config.early_bird.end")


def _timestamp(value: object, field: str) -> int:
    if type(value) is not datetime:
        raise BillingInputError(code="INVALID_TYPE", field=field)
    if type(value.tzinfo) is not timezone or value.fold != 0:
        raise BillingInputError(code="INVALID_TIMESTAMP", field=field)
    offset = value.utcoffset()
    offset_us = (offset.days * 86400 + offset.seconds) * 1_000_000 + offset.microseconds
    if offset_us % 60_000_000:
        raise BillingInputError(code="INVALID_TIMESTAMP", field=field)
    try:
        local = value.astimezone(BEIJING)
    except OverflowError:
        raise BillingInputError(code="DATETIME_OUT_OF_RANGE", field=field) from None
    if not MIN_DATE <= local.date() <= MAX_DATE:
        raise BillingInputError(code="DATETIME_OUT_OF_RANGE", field=field)
    return datetime_to_us(local)


def validate_inputs(
    visits: list[Visit] | tuple[Visit, ...], config: BillingConfig, as_of: datetime | None
) -> tuple[list[_ValidatedVisit], int]:
    _config(config)
    if type(visits) not in (list, tuple):
        raise BillingInputError(code="INVALID_TYPE", field="visits")
    if not visits:
        raise BillingInputError(code="EMPTY_VISITS", field="visits")
    normalized = []
    for index, visit in enumerate(visits):
        path = f"visits[{index}]"
        if type(visit) is not Visit:
            raise BillingInputError(code="INVALID_TYPE", field=path)
        entered = _timestamp(visit.entered_at, f"{path}.entered_at")
        exited = None
        if visit.exited_at is not None:
            exited = _timestamp(visit.exited_at, f"{path}.exited_at")
            if exited <= entered:
                raise BillingInputError(code="INVALID_VISIT_INTERVAL", field=f"{path}.exited_at")
        normalized.append((index, entered, exited))
    seen = set()
    for index, entered, exited in normalized:
        key = (entered, exited)
        if key in seen:
            raise BillingInputError(code="DUPLICATE_VISIT", field=f"visits[{index}]")
        seen.add(key)
    if sum(exited is None for _, _, exited in normalized) > 1:
        raise BillingInputError(code="MULTIPLE_OPEN_VISITS", field="visits")
    normalized.sort(key=lambda item: item[1])
    for index, _, exited in normalized[:-1]:
        if exited is None:
            raise BillingInputError(code="OPEN_VISIT_NOT_LATEST", field=f"visits[{index}].exited_at")
    for previous, following in zip(normalized, normalized[1:]):
        if following[1] < previous[2]:
            raise BillingInputError(code="OVERLAPPING_VISITS", field=f"visits[{following[0]}].entered_at")
    _, entered, exited = normalized[-1]
    if exited is None:
        if as_of is None:
            raise BillingInputError(code="AS_OF_REQUIRED", field="as_of")
        endpoint = _timestamp(as_of, "as_of")
        if endpoint < entered:
            raise BillingInputError(code="AS_OF_BEFORE_ENTRY", field="as_of")
    else:
        if as_of is not None:
            raise BillingInputError(code="AS_OF_NOT_ALLOWED", field="as_of")
        endpoint = exited
    result = [
        _ValidatedVisit(original_index=index, entered_us=start, exited_us=end,
                        end_us=endpoint if end is None else end)
        for index, start, end in normalized
    ]
    return result, result[-1].original_index

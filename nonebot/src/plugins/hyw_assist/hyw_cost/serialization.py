"""Exact, context-independent validation and compact JSON output."""

from datetime import date
from decimal import Decimal

from .errors import BillingInputError
from .models import BillResult, DailyPresenceSeconds
from .validation import MAX_DATE, MAX_INT, MIN_DATE

_DAYS = (MAX_DATE - MIN_DATE).days + 1
_DAY_US = 86400 * 1_000_000
_MAX_CURRENT_US = _DAYS * _DAY_US - 1
_MAX_PAYABLE = (2 * _DAYS + 1) * MAX_INT


def _type(value: object, expected: type, field: str) -> None:
    if type(value) is not expected:
        raise BillingInputError(code="INVALID_TYPE", field=field)


def _duration_us(value: Decimal, maximum: int, field: str) -> int:
    _type(value, Decimal, field)
    if not value.is_finite():
        raise BillingInputError(code="INVALID_RESULT", field=field)
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return 0
    if sign:
        raise BillingInputError(code="INVALID_RESULT", field=field)
    shift = exponent + 6
    if shift < 0:
        cut = -shift
        if cut >= len(digits) or any(digits[-cut:]):
            raise BillingInputError(code="INVALID_RESULT", field=field)
        digits = digits[:-cut]
        shift = 0
    if len(digits) + shift > len(str(maximum)):
        raise BillingInputError(code="INVALID_RESULT", field=field)
    result = int("".join(map(str, digits))) * 10**shift
    if result > maximum:
        raise BillingInputError(code="INVALID_RESULT", field=field)
    return result


def _number(microseconds: int) -> str:
    seconds, remainder = divmod(microseconds, 1_000_000)
    if not remainder:
        return str(seconds)
    return f"{seconds}.{remainder:06d}".rstrip("0")


def serialize_result(result: BillResult) -> str:
    _type(result, BillResult, "result")
    _type(result.stat_date, date, "result.stat_date")
    if not MIN_DATE <= result.stat_date <= MAX_DATE:
        raise BillingInputError(code="INVALID_RESULT", field="result.stat_date")
    presence = result.daily_presence_seconds
    _type(presence, DailyPresenceSeconds, "result.daily_presence_seconds")
    values = {}
    for field in ("early_bird", "day", "night"):
        values[field] = _duration_us(getattr(presence, field), _DAY_US,
                                     f"result.daily_presence_seconds.{field}")
    current = _duration_us(result.current_presence_seconds, _MAX_CURRENT_US,
                           "result.current_presence_seconds")
    payable = result.current_payable_fen
    _type(payable, int, "result.current_payable_fen")
    if not 0 <= payable <= _MAX_PAYABLE:
        raise BillingInputError(code="INVALID_RESULT", field="result.current_payable_fen")
    if values["day"] + values["night"] > _DAY_US:
        raise BillingInputError(code="INVALID_RESULT", field="result.daily_presence_seconds")
    if values["early_bird"] > values["day"] + values["night"]:
        raise BillingInputError(code="INVALID_RESULT", field="result.daily_presence_seconds.early_bird")
    return (
        f'{{"stat_date":"{result.stat_date.isoformat()}","daily_presence_seconds":{{'
        f'"early_bird":{_number(values["early_bird"])},"day":{_number(values["day"])},'
        f'"night":{_number(values["night"])}}},"current_presence_seconds":{_number(current)},'
        f'"current_payable_fen":{payable}}}'
    )

"""One deterministic replay for estimates and final settlements.

All elapsed time is integer microseconds; nominal money is in 1/3600 fen.
Only the final public durations are converted to Decimal.
"""

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from typing import Literal

from .models import BillResult, BillingConfig, DailyPresenceSeconds, Visit
from .validation import BEIJING, datetime_to_us, us_to_beijing, validate_inputs

Kind = Literal["day", "night", "early_bird"]
PeriodId = tuple[Kind, int]
BudgetId = tuple[Kind, int]
SECOND = 1_000_000
HOUR = 3600 * SECOND
DAY = 86400 * SECOND


@dataclass(slots=True, kw_only=True)
class PeriodState:
    kind: Kind
    start_us: int
    end_us: int
    presence_us: int
    nominal_units: int
    assessed_fen: int
    first_hour_covered: bool
    last_context_id: int | None

    @property
    def period_id(self) -> PeriodId:
        return self.kind, self.start_us

    @property
    def has_billing(self) -> bool:
        return self.assessed_fen > 0 or self.first_hour_covered


@dataclass(slots=True, kw_only=True)
class BudgetState:
    budget_id: BudgetId
    limit_fen: int
    used_fen: int

    @property
    def remaining_fen(self) -> int:
        return self.limit_fen - self.used_fen


@dataclass(slots=True, kw_only=True)
class TimingContext:
    context_id: int
    elapsed_us: int
    first_hour_actual_fen: int | None


def _round_fen(units: int) -> int:
    return (units + 1800) // 3600


def _seconds(microseconds: int) -> Decimal:
    return Decimal((0, tuple(int(ch) for ch in str(microseconds)), -6))


def _overlap(start: int, end: int, lower: int, upper: int) -> int:
    return max(0, min(end, upper) - max(start, lower))


class _Replay:
    def __init__(self, visits, config: BillingConfig, current_visit_index: int):
        self.visits = visits
        self.config = config
        self.current_visit_index = current_visit_index
        self.periods: dict[PeriodId, PeriodState] = {}
        self.budgets: dict[BudgetId, BudgetState] = {}
        self.contexts: dict[int, TimingContext] = {}
        self.active_context_id: int | None = None
        self.current_payable_fen = 0
        self.next_context_id = 1

    def _period(self, kind: Kind, start: int, end: int) -> PeriodState:
        key = kind, start
        if key not in self.periods:
            self.periods[key] = PeriodState(
                kind=kind, start_us=start, end_us=end, presence_us=0,
                nominal_units=0, assessed_fen=0, first_hour_covered=False,
                last_context_id=None,
            )
        period = self.periods[key]
        if period.period_id != key or period.end_us != end:
            raise RuntimeError("Conflicting period identity")
        return period

    def _windows(self, instant_us: int) -> list[PeriodState]:
        local = us_to_beijing(instant_us)
        date = local.date()
        day_start = datetime_to_us(datetime.combine(date, self.config.day_start, BEIJING))
        night_start = datetime_to_us(datetime.combine(date, self.config.night_start, BEIJING))
        if instant_us < day_start:
            windows = [self._period("night", night_start - DAY, day_start)]
        elif instant_us < night_start:
            windows = [self._period("day", day_start, night_start)]
        else:
            windows = [self._period("night", night_start, day_start + DAY)]
        early = self.config.early_bird
        if early is not None:
            start = datetime_to_us(datetime.combine(date, early.start, BEIJING))
            end = datetime_to_us(datetime.combine(date, early.end, BEIJING))
            if start <= instant_us < end:
                windows.append(self._period("early_bird", start, end))
        return windows

    def _budget(self, key: BudgetId, limit: int) -> BudgetState:
        if key not in self.budgets:
            self.budgets[key] = BudgetState(budget_id=key, limit_fen=limit, used_fen=0)
        budget = self.budgets[key]
        if budget.budget_id != key or budget.limit_fen != limit:
            raise RuntimeError("Conflicting budget identity")
        return budget

    def _applicable_budgets(self, windows: list[PeriodState]) -> list[BudgetState]:
        base = windows[0]
        base_limit = self.config.day_cap_fen if base.kind == "day" else self.config.night_cap_fen
        budgets = {base.period_id: self._budget(base.period_id, base_limit)}
        if len(windows) == 2:
            owner = windows[-1]
            early = self.config.early_bird
            budgets[owner.period_id] = self._budget(owner.period_id, early.cap_fen)
            date = us_to_beijing(owner.start_us).date()
            day_key = "day", datetime_to_us(datetime.combine(date, self.config.day_start, BEIJING))
            budgets[day_key] = self._budget(day_key, self.config.day_cap_fen)
        return list(budgets.values())

    def _allocate(self, owner: PeriodState, budgets: list[BudgetState],
                  nominal_units: int, visit_index: int) -> int:
        """Advance nominal rounding before applying the deduplicated budgets."""
        proposal = _round_fen(owner.nominal_units + nominal_units) - _round_fen(owner.nominal_units)
        unique = {budget.budget_id: budget for budget in budgets}
        actual = min(proposal, *(budget.remaining_fen for budget in unique.values()))
        owner.nominal_units += nominal_units
        owner.assessed_fen += actual
        for budget in unique.values():
            budget.used_fen += actual
            self._check_budget(budget.budget_id, budget)
        if visit_index == self.current_visit_index:
            self.current_payable_fen += actual
        return actual

    def _context(self) -> TimingContext:
        if self.active_context_id not in self.contexts:
            raise RuntimeError("Missing active context")
        return self.contexts[self.active_context_id]

    def _enter(self, instant_us: int, visit_index: int) -> None:
        windows = self._windows(instant_us)
        owner = windows[-1]
        if owner.has_billing:
            if owner.last_context_id not in self.contexts:
                raise RuntimeError("Missing billed period context")
            self.active_context_id = owner.last_context_id
        else:
            context_id = self.next_context_id
            self.next_context_id += 1
            context = TimingContext(context_id=context_id, elapsed_us=owner.presence_us,
                                    first_hour_actual_fen=None)
            self.contexts[context_id] = context
            self.active_context_id = context_id
            owner.last_context_id = context_id
            if context.elapsed_us > self.config.first_hour_free_seconds * SECOND:
                context.first_hour_actual_fen = self._allocate(
                    owner, self._applicable_budgets(windows),
                    self.config.hourly_rate_fen * 3600, visit_index,
                )
        for period in windows:
            self._check_period(period.period_id, period)
        self._check_context(self.active_context_id, self._context())

    def _advance(self, start_us: int, end_us: int, visit_index: int) -> None:
        windows = self._windows(start_us)
        owner = windows[-1]
        context = self._context()
        a = context.elapsed_us
        b = a + end_us - start_us
        for period in windows:
            period.presence_us += end_us - start_us
        owner.last_context_id = context.context_id
        g = self.config.first_hour_free_seconds * SECOND
        if context.first_hour_actual_fen is None and b > g:
            context.first_hour_actual_fen = self._allocate(
                owner, self._applicable_budgets(windows),
                self.config.hourly_rate_fen * 3600, visit_index,
            )
        q = self.config.step_seconds * SECOND
        steps = max(b - HOUR, 0) // q - max(a - HOUR, 0) // q
        if steps:
            self._allocate(owner, self._applicable_budgets(windows),
                           steps * self.config.hourly_rate_fen * self.config.step_seconds,
                           visit_index)
        if (context.first_hour_actual_fen is not None and context.first_hour_actual_fen > 0
                and max(a, g) < min(b, HOUR)):
            for period in windows:
                period.first_hour_covered = True
                period.last_context_id = context.context_id
        context.elapsed_us = b
        for period in windows:
            self._check_period(period.period_id, period)
        self._check_context(context.context_id, context)

    def _slice_end(self, instant_us: int, end_us: int) -> int:
        date = us_to_beijing(instant_us).date()
        midnight = datetime_to_us(datetime.combine(date, time(), BEIJING))
        candidates = [end_us, midnight + DAY]
        candidates.extend(period.end_us for period in self._windows(instant_us))
        early = self.config.early_bird
        if early is not None:
            early_start = datetime_to_us(datetime.combine(date, early.start, BEIJING))
            if early_start > instant_us:
                candidates.append(early_start)
        return min(candidates)

    def _check_invariants(self) -> None:
        if self.active_context_id is not None and self.active_context_id not in self.contexts:
            raise RuntimeError("Dangling active context")
        for key, period in self.periods.items():
            self._check_period(key, period)
        for key, budget in self.budgets.items():
            self._check_budget(key, budget)
        for key, context in self.contexts.items():
            self._check_context(key, context)

    def _check_period(self, key: PeriodId, period: PeriodState) -> None:
        if (key != period.period_id or period.start_us >= period.end_us
                or not 0 <= period.presence_us <= period.end_us - period.start_us
                or period.nominal_units < 0
                or not 0 <= period.assessed_fen <= _round_fen(period.nominal_units)
                or (period.last_context_id is not None and period.last_context_id not in self.contexts)
                or (period.has_billing and period.last_context_id is None)):
            raise RuntimeError("Invalid period state")

    @staticmethod
    def _check_budget(key: BudgetId, budget: BudgetState) -> None:
        if key != budget.budget_id or budget.limit_fen <= 0 or not 0 <= budget.used_fen <= budget.limit_fen:
            raise RuntimeError("Invalid budget state")

    def _check_context(self, key: int, context: TimingContext) -> None:
        if (key != context.context_id or context.elapsed_us < 0
                or (context.first_hour_actual_fen is None
                    and context.elapsed_us > self.config.first_hour_free_seconds * SECOND)
                or (context.first_hour_actual_fen is not None
                    and not 0 <= context.first_hour_actual_fen <= self.config.hourly_rate_fen)):
            raise RuntimeError("Invalid timing context")

    def run(self) -> BillResult:
        for visit in self.visits:
            self._enter(visit.entered_us, visit.original_index)
            instant = visit.entered_us
            while instant < visit.end_us:
                end = self._slice_end(instant, visit.end_us)
                self._advance(instant, end, visit.original_index)
                instant = end
            if visit.exited_us is not None:
                self.active_context_id = None
        self._check_invariants()
        return self._result()

    def _result(self) -> BillResult:
        current = self.visits[-1]
        stat_date = us_to_beijing(current.end_us).date()
        midnight = datetime_to_us(datetime.combine(stat_date, time(), BEIJING))
        day_start = datetime_to_us(datetime.combine(stat_date, self.config.day_start, BEIJING))
        night_start = datetime_to_us(datetime.combine(stat_date, self.config.night_start, BEIJING))
        total = day = early = 0
        for visit in self.visits:
            start, end = max(visit.entered_us, midnight), min(visit.end_us, midnight + DAY)
            total += max(0, end - start)
            day += _overlap(start, end, day_start, night_start)
            if self.config.early_bird is not None:
                early += _overlap(
                    start, end,
                    datetime_to_us(datetime.combine(stat_date, self.config.early_bird.start, BEIJING)),
                    datetime_to_us(datetime.combine(stat_date, self.config.early_bird.end, BEIJING)),
                )
        return BillResult(
            stat_date=stat_date,
            daily_presence_seconds=DailyPresenceSeconds(
                early_bird=_seconds(early), day=_seconds(day), night=_seconds(total - day)),
            current_presence_seconds=_seconds(current.end_us - current.entered_us),
            current_payable_fen=self.current_payable_fen,
        )


def calculate_bill(visits: list[Visit] | tuple[Visit, ...], config: BillingConfig, *,
                   as_of: datetime | None = None) -> BillResult:
    normalized, current_visit_index = validate_inputs(visits, config, as_of)
    return _Replay(normalized, config, current_visit_index).run()

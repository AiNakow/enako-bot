"""Stable error categories and read-only machine-readable details."""


class BillingError(ValueError):
    __slots__ = ("_code", "_field")

    def __init__(self, *, code: str, field: str) -> None:
        super().__init__(f"{code}: {field}")
        self._code = code
        self._field = field

    @property
    def code(self) -> str:
        return self._code

    @property
    def field(self) -> str:
        return self._field


class BillingInputError(BillingError):
    pass


class BillingConfigError(BillingError):
    pass

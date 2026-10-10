"""Strict startup-only JSON configuration; no business parameters live here."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, StrictBool, TypeAdapter, ValidationError, field_validator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GROUP_KEY_PATTERN = r"(?:qq:[^\s:]{1,256}|onebot11:[1-9][0-9]{0,255})"


class Config(BaseModel):
    group_config_file: Path = Path("plugin_data/group_config.json")

    @field_validator("group_config_file", mode="before")
    @classmethod
    def validate_file_path(cls, value: Any) -> Any:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("expected a nonempty path string")
        return value


class GroupOverride(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    enabled: StrictBool


class PluginPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    default_enabled: StrictBool
    private_enabled: StrictBool
    groups: dict[str, GroupOverride]


POLICIES = TypeAdapter(dict[str, PluginPolicy])


def validate_group_key(group_key: str) -> None:
    if not isinstance(group_key, str) or re.fullmatch(GROUP_KEY_PATTERN, group_key) is None:
        raise ValueError("invalid group key")


def validation_locations(error: ValidationError) -> str:
    # Do not stringify ValidationError: it includes the original configuration.
    return "; ".join(
        f"$.{'.'.join(map(str, item['loc']))}: {item['type']}"
        for item in error.errors(include_input=False)
    )


class _FormatError(ValueError):
    pass


@dataclass
class _JSONObject:
    values: dict[str, Any]
    duplicates: list[str]


def _object_pairs(pairs: list[tuple[str, Any]]) -> _JSONObject:
    values: dict[str, Any] = {}
    duplicates = []
    for key, value in pairs:
        if key in values:
            duplicates.append(key)
        values[key] = value
    return _JSONObject(values, duplicates)


def _materialize(value: Any, location: str = "$") -> Any:
    if isinstance(value, _JSONObject):
        if value.duplicates:
            raise _FormatError(f"{location}.{value.duplicates[0]}: duplicate_key")
        return {key: _materialize(item, f"{location}.{key}") for key, item in value.values.items()}
    if isinstance(value, list):
        return [_materialize(item, f"{location}[{index}]") for index, item in enumerate(value)]
    return value


def _reject_constant(value: str) -> None:
    raise _FormatError("$: non_standard_number")


def read_policies(path: Path, known_business_plugins: frozenset[str]) -> dict[str, PluginPolicy]:
    try:
        if not path.is_file():
            raise _FormatError("$: expected_readable_regular_file")
        raw = path.read_text(encoding="utf-8")
        value = _materialize(json.loads(raw, object_pairs_hook=_object_pairs, parse_constant=_reject_constant))
        policies = POLICIES.validate_python(value, strict=True)
        for name, policy in policies.items():
            if name not in known_business_plugins:
                raise _FormatError(f"$.{name}: unknown_business_plugin")
            for group_key in policy.groups:
                try:
                    validate_group_key(group_key)
                except ValueError:
                    raise _FormatError(f"$.{name}.groups.{group_key}: invalid_group_key") from None
        return policies
    except ValidationError as error:
        reason = validation_locations(error)
    except json.JSONDecodeError as error:
        reason = f"$: invalid_json at line {error.lineno}, column {error.colno}"
    except (OSError, UnicodeError) as error:
        reason = f"$: {type(error).__name__}"
    except _FormatError as error:
        reason = str(error)
    raise RuntimeError(f"Invalid group config {path}: {reason}") from None

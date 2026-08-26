from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1]
RESULT_PREFIX = "LOADED_PLUGINS="


def _loaded_plugins_for(
    adapter: str,
    enabled_plugins: list[str] | None = None,
) -> set[str]:
    env = os.environ.copy()
    env["BOT_ADAPTER"] = adapter
    env.pop("ENABLED_PLUGINS", None)
    if enabled_plugins is not None:
        env["ENABLED_PLUGINS"] = json.dumps(enabled_plugins)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, nonebot, bot; "
                f"print({RESULT_PREFIX!r} + json.dumps(sorted("
                "plugin.id_ for plugin in nonebot.get_loaded_plugins())))"
            ),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    output = next(
        line.removeprefix(RESULT_PREFIX)
        for line in result.stdout.splitlines()
        if line.startswith(RESULT_PREFIX)
    )
    return set(json.loads(output))


@pytest.mark.parametrize(
    ("adapter", "command_panel_loaded"),
    [("qq", True), ("onebot11", False)],
)
def test_command_panel_is_only_loaded_for_qq_adapter(
    adapter: str,
    command_panel_loaded: bool,
) -> None:
    loaded_plugins = _loaded_plugins_for(adapter)

    assert "_adapter" in loaded_plugins
    assert ("qq_command_panel" in loaded_plugins) is command_panel_loaded
    assert {"bot_assist", "gsz-assist", "mahjong-assist"} <= loaded_plugins


@pytest.mark.parametrize(
    ("adapter", "enabled_plugins", "expected_plugins"),
    [
        (
            "qq",
            ["bot_assist", "qq_command_panel"],
            {"_adapter", "bot_assist", "qq_command_panel"},
        ),
        (
            "onebot11",
            ["bot_assist", "qq_command_panel"],
            {"_adapter", "bot_assist"},
        ),
        ("qq", [], {"_adapter"}),
    ],
)
def test_enabled_plugins_filters_available_plugins(
    adapter: str,
    enabled_plugins: list[str],
    expected_plugins: set[str],
) -> None:
    assert _loaded_plugins_for(adapter, enabled_plugins) == expected_plugins

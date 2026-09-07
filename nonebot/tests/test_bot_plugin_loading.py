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
    workdir: Path,
    adapter: str,
    enabled_plugins: list[str] | None = None,
) -> set[str]:
    # Isolate dotenv files, process configuration and formula data directories.
    (workdir / "src").symlink_to(PROJECT_ROOT / "src", target_is_directory=True)
    (workdir / "bot.py").symlink_to(PROJECT_ROOT / "bot.py")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT", "TMPDIR") if key in os.environ}
    env["BOT_ADAPTER"] = adapter
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"""
import importlib.util, json, pathlib, sys
import nonebot
nonebot.init(
    _env_file=[str(pathlib.Path.cwd() / 'unused-test.env')],
    driver='~fastapi+~httpx', log_level='WARNING',
    bot_adapter={adapter!r}, enabled_plugins={enabled_plugins!r},
)
spec = importlib.util.spec_from_file_location(
    'src.plugins.gsz-assist.common', 'src/plugins/gsz-assist/common.py',
)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
common.data_dir = str(pathlib.Path.cwd() / 'gsz-data')
common.database_dir = str(pathlib.Path(common.data_dir) / 'database')
common.gsz_userdata_file = str(pathlib.Path(common.database_dir) / 'gsz_userdata.db')
common.gsz_ratedata_file = str(pathlib.Path(common.database_dir) / 'gsz_ratedata.db')
sys.modules[spec.name] = common
import bot
print({RESULT_PREFIX!r} + json.dumps(sorted(
    plugin.id_ for plugin in nonebot.get_loaded_plugins()
)))
""",
        ],
        cwd=workdir,
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
    tmp_path: Path,
    adapter: str,
    command_panel_loaded: bool,
) -> None:
    loaded_plugins = _loaded_plugins_for(tmp_path, adapter)

    assert "_adapter" in loaded_plugins
    assert ("qq_command_panel" in loaded_plugins) is command_panel_loaded
    assert {"bot_assist", "gsz-assist", "mahjong-assist"} <= loaded_plugins


@pytest.mark.parametrize(
    ("adapter", "enabled_plugins", "expected_plugins"),
    [
        (
            "qq",
            ["bot_assist"],
            {"_adapter", "bot_assist", "qq_command_panel"},
        ),
        (
            "onebot11",
            ["bot_assist"],
            {"_adapter", "bot_assist"},
        ),
        ("qq", [], {"_adapter", "qq_command_panel"}),
        ("onebot11", [], {"_adapter"}),
    ],
)
def test_enabled_plugins_filters_available_plugins(
    tmp_path: Path,
    adapter: str,
    enabled_plugins: list[str],
    expected_plugins: set[str],
) -> None:
    assert _loaded_plugins_for(tmp_path, adapter, enabled_plugins) == expected_plugins


@pytest.mark.parametrize("adapter", ["qq", "onebot11"])
def test_command_panel_cannot_be_selected_as_business_plugin(tmp_path: Path, adapter: str) -> None:
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, adapter, ["qq_command_panel"])
    assert "Unknown ENABLED_PLUGINS: qq_command_panel" in exc.value.stderr


def test_plugin_loading_ignores_host_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text('BOT_ADAPTER=invalid\nENABLED_PLUGINS=["does-not-exist"]\n', encoding="utf-8")
    monkeypatch.setenv("BOT_ADAPTER", "invalid")
    monkeypatch.setenv("ENABLED_PLUGINS", '["does-not-exist"]')
    monkeypatch.setenv("DRIVER", "invalid")
    assert _loaded_plugins_for(tmp_path, "qq", []) == {"_adapter", "qq_command_panel"}

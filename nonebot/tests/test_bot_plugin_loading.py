from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import coverage


PROJECT_ROOT = Path(__file__).parents[1]
RESULT_PREFIX = "LOADED_PLUGINS="


def _loaded_plugins_for(
    workdir: Path,
    adapter: str,
    enabled_plugins: list[str] | None = None,
    *,
    config_text: str | None = "{}",
    failing_plugin: str | None = None,
    group_config_file: str | None = None,
    run_main: bool = False,
    camera_configured: bool = True,
) -> set[str]:
    # Isolate dotenv files, process configuration and formula data directories.
    if not (workdir / "src").exists():
        (workdir / "src").symlink_to(PROJECT_ROOT / "src", target_is_directory=True)
    (workdir / "bot.py").symlink_to(PROJECT_ROOT / "bot.py")
    config_path = workdir / "group_config.json"
    if config_text is not None:
        config_path.write_text(config_text, encoding="utf-8")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "SYSTEMROOT", "TMPDIR") if key in os.environ}
    env["BOT_ADAPTER"] = adapter
    script = workdir / "startup.py"
    script.write_text(f"""
import importlib.util, json, pathlib, sys, runpy
import nonebot
nonebot.init(
    _env_file=[str(pathlib.Path.cwd() / 'unused-test.env')],
    driver='~fastapi+~httpx', log_level='WARNING',
    bot_adapter={adapter!r}, enabled_plugins={enabled_plugins!r},
    group_config_file={group_config_file if group_config_file is not None else str(config_path)!r},
    **({{'people_counter_device_serial': 'TEST-DEVICE', 'people_counter_access_token': 'test-token'}} if {camera_configured!r} else {{}}),
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
spec = importlib.util.spec_from_file_location(
    'src.plugins.mahjong-assist.common', 'src/plugins/mahjong-assist/common.py',
)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
common.data_dir = str(pathlib.Path.cwd() / 'mahjong-data')
common.data_collection_file = str(pathlib.Path(common.data_dir) / 'images.txt')
sys.modules[spec.name] = common
original_load = nonebot.load_plugin
def load(path):
    if path == {failing_plugin!r}:
        return None
    return original_load(path)
nonebot.load_plugin = load
nonebot.run = lambda: print('RUN_REACHED')
if {run_main!r}:
    runpy.run_path('bot.py', run_name='__main__')
else:
    import bot
print({RESULT_PREFIX!r} + json.dumps(sorted(
    plugin.id_ for plugin in nonebot.get_loaded_plugins()
)))
""", encoding="utf-8")
    command = [sys.executable, str(script)]
    current_coverage = coverage.Coverage.current()
    if current_coverage is not None:
        env["COVERAGE_FILE"] = str(Path(current_coverage.config.data_file).resolve())
        command = [sys.executable, "-m", "coverage", "run", "--parallel-mode", "--branch", "--source=src,bot", str(script)]
    result = subprocess.run(
        command,
        cwd=workdir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
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
    assert "group_config" in loaded_plugins
    assert ("qq_command_panel" in loaded_plugins) is command_panel_loaded
    assert {"bot_assist", "gsz-assist", "mahjong-assist", "hyw_assist"} <= loaded_plugins


@pytest.mark.parametrize(
    ("adapter", "enabled_plugins", "expected_plugins"),
    [
        (
            "qq",
            ["bot_assist"],
            {"_adapter", "group_config", "bot_assist", "qq_command_panel"},
        ),
        (
            "onebot11",
            ["bot_assist"],
            {"_adapter", "group_config", "bot_assist"},
        ),
        ("qq", [], {"_adapter", "group_config", "qq_command_panel"}),
        ("onebot11", [], {"_adapter", "group_config"}),
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
    assert _loaded_plugins_for(tmp_path, "qq", []) == {"_adapter", "group_config", "qq_command_panel"}


@pytest.mark.parametrize("adapter", ["qq", "onebot11"])
def test_group_config_cannot_be_selected(tmp_path, adapter):
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, adapter, ["group_config"])
    assert "group_config cannot be selected in ENABLED_PLUGINS" in exc.value.stderr


@pytest.mark.parametrize("raw", [None, "", "[]", '{"hyw_assist":{"default_enabled":false,"private_enabled":false,"groups":{"onebot11:01":{"enabled":false}}}}', '{"bot_assist":{"default_enabled":"SECRET-MARKER","private_enabled":true,"groups":{}}}'])
@pytest.mark.parametrize("adapter", ["qq", "onebot11"])
def test_invalid_config_exits_before_run_and_business_loading(tmp_path, raw, adapter):
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, adapter, ["bot_assist"], config_text=raw, run_main=True)
    output = exc.value.stdout + exc.value.stderr
    assert "RUN_REACHED" not in output
    assert 'Succeeded to load plugin "bot_assist"' not in output
    assert "Invalid group config" in output
    assert "SECRET-MARKER" not in output


@pytest.mark.parametrize("plugin", ["src.infrastructure_plugins._adapter", "src.infrastructure_plugins.group_config", "src.infrastructure_plugins.qq_command_panel", "src.plugins.bot_assist", "nonebot_plugin_htmlrender"])
def test_selected_plugin_failure_is_fatal(tmp_path, plugin):
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, "qq", ["bot_assist", "nonebot_plugin_htmlrender"], failing_plugin=plugin, run_main=True)
    assert "Failed to load" in exc.value.stderr
    assert "RUN_REACHED" not in exc.value.stdout


def test_unavailable_camera_configuration_is_fatal(tmp_path):
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, "qq", ["hyw_assist"], camera_configured=False)
    assert "Failed to load selected plugin: hyw_assist" in exc.value.stderr


def test_policy_does_not_load_globally_disabled_plugin(tmp_path):
    raw = '{"hyw_assist":{"default_enabled":true,"private_enabled":true,"groups":{}}}'
    assert _loaded_plugins_for(tmp_path, "qq", [], config_text=raw) == {"_adapter", "group_config", "qq_command_panel"}


def test_config_environment_path_is_validated(tmp_path):
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, "qq", [], group_config_file="  ")
    assert "Invalid GROUP_CONFIG_FILE" in exc.value.stderr


def test_unsupported_adapter_fails(tmp_path):
    with pytest.raises(subprocess.CalledProcessError) as exc:
        _loaded_plugins_for(tmp_path, "unknown", [])
    assert "Unsupported BOT_ADAPTER" in exc.value.stderr


def test_valid_config_reaches_main_run(tmp_path):
    assert _loaded_plugins_for(tmp_path, "onebot11", [], run_main=True) == {"_adapter", "group_config"}


def test_qq_only_discovered_plugin_can_be_configured_without_loading(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/plugins").symlink_to(PROJECT_ROOT / "src/plugins", target_is_directory=True)
    (tmp_path / "src/infrastructure_plugins").symlink_to(PROJECT_ROOT / "src/infrastructure_plugins", target_is_directory=True)
    (tmp_path / "src/qq_adapter.py").symlink_to(PROJECT_ROOT / "src/qq_adapter.py")
    (tmp_path / "src/qq_plugins").mkdir()
    (tmp_path / "src/qq_plugins/qq_test.py").write_text("# local QQ business plugin\n")
    raw = '{"qq_test":{"default_enabled":false,"private_enabled":false,"groups":{}}}'
    assert _loaded_plugins_for(tmp_path, "onebot11", ["qq_test"], config_text=raw) == {"_adapter", "group_config"}

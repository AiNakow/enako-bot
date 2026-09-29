import asyncio
from dataclasses import replace
import importlib
import importlib.util
from io import BytesIO
from pathlib import Path
import sys
import threading
import types
from unittest.mock import AsyncMock, Mock

import nonebot
from nonebot.exception import FinishedException
from PIL import Image
import pytest

PLUGIN_PATH = Path(__file__).parents[1] / "src/plugins/hyw_assist"
PACKAGE = "hyw_assist_testpkg"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(PLUGIN_PATH)]
sys.modules[PACKAGE] = package
service_module = importlib.import_module(f"{PACKAGE}.person_counter.service")
areas_module = importlib.import_module(f"{PACKAGE}.person_counter.machine_areas")
Camera = service_module.Camera
CounterError = service_module.CounterError


def rectangle(x1, y1, x2, y2):
    return ((x1, y1), (x2, y1), (x2, y2), (x1, y2))


@pytest.fixture
def counter(monkeypatch):
    areas = areas_module.MachineAreas((100, 100), .6, tuple(
        areas_module.MachineArea(name, limit, rectangle(x, 0, x + 30, 80))
        for name, limit, x in [("中二", 1, 0), ("舞萌左", 2, 30), ("舞萌右", 2, 60)]))
    settings = service_module.Settings(
        Camera("TEST"), access_token="test-token", machine_areas=areas,
        exclusion_regions=service_module.ExclusionRegions(
            (100, 100), (rectangle(0, 80, 100, 100),), .6))
    capture = Mock()
    with Image.new("RGB", (100, 100)) as image:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
    capture.capture.return_value = buffer.getvalue()
    # Two at 中二 (capped), one at each 舞萌, a bystander, a reflection,
    # a duplicate, a non-person, and a low-confidence detection.
    boxes = [[1, 1, 10, 20], [15, 1, 25, 20], [31, 1, 40, 20],
             [61, 1, 70, 20], [91, 1, 99, 20], [1, 81, 10, 99],
             [1, 1, 10, 20], [41, 1, 50, 20], [71, 1, 80, 20]]
    model = Mock()
    model.predict.return_value = (boxes, [0] * 7 + [1, 0], [.9] * 8 + [.1])
    monkeypatch.setattr(service_module, "CaptureClient", Mock(return_value=capture))
    monkeypatch.setattr(service_module, "OnnxDetector", Mock(return_value=model))
    with service_module.PeopleCounter(settings) as instance:
        yield instance, capture, model


def test_combined_single_capture_and_inference(counter):
    instance, capture, model = counter
    assert asyncio.run(instance.count_with_occupancy_async()) == (
        5, {"中二": 1, "舞萌左": 1, "舞萌右": 1})
    capture.capture.assert_called_once_with(instance.settings.camera)
    model.predict.assert_called_once()
    with pytest.raises(ValueError):
        model.predict.call_args.args[0].getpixel((0, 0))


def test_empty_detection(counter):
    instance, _, model = counter
    model.predict.return_value = ([], [], [])
    assert instance.count_with_occupancy() == (0, {"中二": 0, "舞萌左": 0, "舞萌右": 0})


def test_explicit_default_camera(counter):
    instance, capture, _ = counter
    instance.count_with_occupancy(Camera("test"))
    capture.capture.assert_called_once_with(instance.settings.camera)


@pytest.mark.parametrize("camera", [Camera("OTHER"), Camera("TEST", 2)])
def test_reject_other_camera(counter, camera):
    instance, capture, model = counter
    with pytest.raises(CounterError, match="默认摄像头"):
        asyncio.run(instance.count_with_occupancy_async(camera))
    capture.capture.assert_not_called()
    model.predict.assert_not_called()


def test_missing_machine_areas(counter):
    instance, capture, _ = counter
    instance.settings = replace(instance.settings, machine_areas=None)
    with pytest.raises(CounterError, match="未配置"):
        instance.count_with_occupancy()
    capture.capture.assert_not_called()


@pytest.mark.parametrize("failure", ["capture", "decode", "predict", "model", "closed"])
def test_failures(counter, failure):
    instance, capture, model = counter
    if failure == "capture":
        capture.capture.side_effect = CounterError("抓拍失败")
    elif failure == "decode":
        capture.capture.return_value = b"invalid-image"
    elif failure == "predict":
        model.predict.side_effect = RuntimeError("failed")
    elif failure == "model":
        service_module.OnnxDetector.side_effect = RuntimeError("failed")
    else:
        instance.close()
    with pytest.raises(CounterError):
        asyncio.run(instance.count_with_occupancy_async())
    if failure in {"model", "closed"}:
        capture.capture.assert_not_called()


@pytest.mark.parametrize("method", ["count_async", "machine_occupancy_async",
                                    "count_image", "machine_occupancy_image"])
def test_existing_interfaces(counter, tmp_path, method):
    instance, capture, model = counter
    if method.endswith("image"):
        path = tmp_path / "capture.png"
        path.write_bytes(capture.capture.return_value)
        result = getattr(instance, method)(path)
        capture.capture.assert_not_called()
    else:
        result = asyncio.run(getattr(instance, method)())
        capture.capture.assert_called_once()
    assert result == ({"中二": 1, "舞萌左": 1, "舞萌右": 1}
                      if method.startswith("machine") else 5)
    model.predict.assert_called_once()


def test_runs_in_worker_thread(counter):
    instance, capture, _ = counter
    caller_thread = threading.get_ident()
    data = capture.capture.return_value

    def capture_in_thread(camera):
        assert threading.get_ident() != caller_thread
        return data

    capture.capture.side_effect = capture_in_thread
    asyncio.run(instance.count_with_occupancy_async())


@pytest.fixture
def handler(counter, monkeypatch):
    instance, _, _ = counter
    config = importlib.import_module(f"{PACKAGE}.config")
    monkeypatch.setattr(config, "create_service", lambda: instance)
    matcher = Mock()
    matcher.handle.return_value = lambda function: function
    matcher.finish = AsyncMock(side_effect=FinishedException)
    monkeypatch.setattr(nonebot, "on_keyword", Mock(return_value=matcher))
    driver = Mock()
    driver.on_shutdown.side_effect = lambda function: function
    monkeypatch.setattr(nonebot, "get_driver", Mock(return_value=driver))
    spec = importlib.util.spec_from_file_location(PACKAGE, PLUGIN_PATH / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, matcher


def test_handler_capture_to_reply(counter, handler):
    instance, capture, model = counter
    module, matcher = handler
    with pytest.raises(FinishedException):
        asyncio.run(module.handle_people_count())
    matcher.finish.assert_awaited_once_with(
        "音游房当前有 5 人。\n当前已上机人数：\n中二：1 人\n舞萌左：1 人\n舞萌右：1 人\n（当前结果基于监控图像识别）")
    capture.capture.assert_called_once_with(instance.settings.camera)
    model.predict.assert_called_once()
    assert not module.busy.locked()


def test_handler_failure(counter, handler):
    _, capture, _ = counter
    module, matcher = handler
    capture.capture.side_effect = CounterError("抓拍失败")
    with pytest.raises(FinishedException):
        asyncio.run(module.handle_people_count())
    matcher.finish.assert_awaited_once_with("人数检测失败，请检查摄像头连接、配置或模型。")
    assert not module.busy.locked()


def test_handler_busy(counter, handler):
    _, capture, _ = counter
    module, matcher = handler

    async def run():
        async with module.busy:
            with pytest.raises(FinishedException):
                await module.handle_people_count()

    asyncio.run(run())
    matcher.finish.assert_awaited_once_with("检测人数中，请不要频繁查询。")
    capture.capture.assert_not_called()


def test_shutdown(counter, handler):
    instance, capture, _ = counter
    module, _ = handler
    asyncio.run(module.shutdown())
    capture.close.assert_called_once()
    assert instance._closed


def test_bundled_model_capture_to_reply(counter, handler):
    instance, capture, _ = counter
    module, matcher = handler
    detector = importlib.import_module(f"{PACKAGE}.person_counter.detector")
    instance._model = detector.OnnxDetector(
        instance.settings.model_path, instance.settings.image_size, instance.settings.threads)
    with pytest.raises(FinishedException):
        asyncio.run(module.handle_people_count())
    matcher.finish.assert_awaited_once_with(
        "音游房当前有 0 人。\n当前已上机人数：\n中二：0 人\n舞萌左：0 人\n舞萌右：0 人\n（当前结果基于监控图像识别）")
    capture.capture.assert_called_once()

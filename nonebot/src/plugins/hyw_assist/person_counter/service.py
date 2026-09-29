from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from io import BytesIO
import math
from pathlib import Path
import re
import threading

from PIL import Image, ImageOps

from .capture import CaptureClient, CounterError
from .regions import ExclusionRegions
from .machine_areas import MachineAreas
from .postprocess import process_detections
from .detector import OnnxDetector

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Camera:
    device_serial: str
    channel_no: int = 1

    def __post_init__(self):
        serial = self.device_serial.strip().upper()
        if not re.fullmatch(r"[A-Z0-9-]{1,50}", serial):
            raise CounterError("设备序列号格式无效。")
        if type(self.channel_no) is not int or not 1 <= self.channel_no <= 65535:
            raise CounterError("通道号必须为 1..65535 的整数。")
        object.__setattr__(self, "device_serial", serial)


@dataclass(frozen=True)
class Settings:
    camera: Camera
    app_key: str = field(default="", repr=False)
    app_secret: str = field(default="", repr=False)
    access_token: str = field(default="", repr=False)
    model_path: Path = ROOT / "models/yolo26n.onnx"
    threads: int = 2
    confidence: float = 0.25
    image_size: int = 640
    capture_interval: float = 5
    timeout: float = 40
    exclusion_regions: ExclusionRegions | None = None
    machine_areas: MachineAreas | None = field(
        default_factory=lambda: MachineAreas.load(ROOT / "machine_areas.json"))
    nms_iou: float = 0.5

    def __post_init__(self):
        if not self.access_token and not (self.app_key and self.app_secret):
            raise CounterError("请配置 AppKey/AppSecret 或授权 AccessToken。")
        for name, value, low, high in [
            ("PEOPLE_COUNTER_CONFIDENCE", self.confidence, 0.01, 1),
            ("PEOPLE_COUNTER_IMAGE_SIZE", self.image_size, 320, 4096),
            ("PEOPLE_COUNTER_THREADS", self.threads, 1, 64),
            ("PEOPLE_COUNTER_CAPTURE_INTERVAL", self.capture_interval, 5, 3600),
            ("PEOPLE_COUNTER_HTTP_TIMEOUT", self.timeout, 1, 300),
            ("PEOPLE_COUNTER_NMS_IOU", self.nms_iou, 0, 1),
        ]:
            if not math.isfinite(value) or not low <= value <= high:
                raise CounterError(f"{name} 应在 {low}..{high} 范围内。")
        if self.image_size % 32:
            raise CounterError("PEOPLE_COUNTER_IMAGE_SIZE 必须为 32 的倍数。")

class PeopleCounter:
    """单进程复用一个实例；同步/异步调用共享锁，避免模型并发访问。"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._capture = CaptureClient(settings)
        self._model = None
        self._lock = threading.Lock()
        self._closed = False

    def _load_model(self):
        if self._model is None:
            try:
                self._model = OnnxDetector(self.settings.model_path, self.settings.image_size, self.settings.threads)
            except Exception:
                raise CounterError("ONNX 模型加载失败，请检查模型路径和 onnxruntime 安装。") from None

    def _detect(self, image: Image.Image, apply_regions=True):
        try:
            boxes, labels, scores = self._model.predict(image, self.settings.confidence)
            return process_detections(boxes, labels, scores, image.size, self.settings.confidence,
                self.settings.exclusion_regions if apply_regions else None, self.settings.nms_iou)
        except CounterError:
            raise
        except Exception:
            raise CounterError("YOLO 人数检测失败，请检查运行设备及模型兼容性。") from None

    def _infer(self, image: Image.Image, apply_regions=True) -> int:
        return sum(not detection["excluded"]
                   for detection in self._detect(image, apply_regions))

    def _infer_machine_occupancy(self, image: Image.Image, apply_regions=True):
        if self.settings.machine_areas is None:
            raise CounterError("未配置音游机器游玩区域。")
        detections = self._detect(image, apply_regions)
        return self.settings.machine_areas.count(detections, image.size)

    def count(self, camera: Camera | None = None) -> int:
        """抓取当前画面并返回人数；未检测到人为 0，失败抛 CounterError。"""
        with self._lock:
            self._check_open()
            self._load_model()  # 依赖不可用时不消耗抓拍额度
            target = camera or self.settings.camera
            data = self._capture.capture(target)
            # 该标定仅绑定 .env 的默认摄像头，不误用于其他 NVR/通道。
            return self._process_bytes(data, self._infer,
                                       apply_regions=target == self.settings.camera)

    def count_image(self, path: str | Path) -> int:
        """离线验证现有图片，不请求摄像头。"""
        with self._lock:
            self._check_open()
            self._load_model()
            try:
                data = Path(path).read_bytes()
            except OSError:
                raise CounterError("无法读取本地图片。") from None
            return self._process_bytes(data, self._infer)

    def _process_bytes(self, data, processor, apply_regions=True):
        try:
            with Image.open(BytesIO(data)) as original:
                if original.width * original.height > 25_000_000:
                    raise CounterError("图片分辨率超过 2500 万像素。")
                image = ImageOps.exif_transpose(original).convert("RGB")
                image.load()
        except CounterError:
            raise
        except Exception:
            raise CounterError("抓拍内容不是可解码的图片。") from None
        try:
            return processor(image, apply_regions=apply_regions)
        finally:
            image.close()

    async def count_async(self, camera: Camera | None = None) -> int:
        """用于 NoneBot handler；HTTP/模型推理和限流等待不阻塞事件循环。"""
        return await asyncio.to_thread(self.count, camera)

    def machine_occupancy(self, camera: Camera | None = None) -> dict[str, int]:
        """抓取默认机位并返回中二、舞萌左、舞萌右的上机人数。"""
        with self._lock:
            self._check_open()
            self._load_model()
            target = camera or self.settings.camera
            if target != self.settings.camera:
                raise CounterError("音游机器游玩区域仅对默认摄像头完成标定。")
            data = self._capture.capture(target)
            return self._process_bytes(data, self._infer_machine_occupancy)

    def machine_occupancy_image(self, path: str | Path) -> dict[str, int]:
        """使用同机位本地图片离线验证各机器的上机人数。"""
        with self._lock:
            self._check_open()
            self._load_model()
            try:
                data = Path(path).read_bytes()
            except OSError:
                raise CounterError("无法读取本地图片。") from None
            return self._process_bytes(data, self._infer_machine_occupancy)

    async def machine_occupancy_async(self, camera: Camera | None = None) -> dict[str, int]:
        """NoneBot 异步接口，不阻塞事件循环。"""
        return await asyncio.to_thread(self.machine_occupancy, camera)

    def _check_open(self):
        if self._closed:
            raise CounterError("人数统计服务已关闭。")

    def close(self):
        with self._lock:
            if not self._closed:
                self._capture.close()
                self._model = None
                self._closed = True

    async def aclose(self):
        await asyncio.to_thread(self.close)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

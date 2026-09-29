"""读取 NoneBot 已解析的配置，不自行读取 dotenv 或 os.environ。"""
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr

from .person_counter import Camera, PeopleCounter, Settings
from .person_counter.regions import ExclusionRegions
from .person_counter.machine_areas import MachineAreas

BUNDLE_ROOT = Path(__file__).resolve().parent


class Config(BaseModel):
    people_counter_app_key: SecretStr = SecretStr("")
    people_counter_app_secret: SecretStr = SecretStr("")
    people_counter_access_token: SecretStr = SecretStr("")
    people_counter_device_serial: str
    people_counter_channel_no: int = Field(default=1, ge=1, le=65535)
    people_counter_model_path: str = "person_counter/models/yolo26n.onnx"
    people_counter_threads: int = Field(default=2, ge=1, le=64)
    people_counter_confidence: float = Field(default=.25, ge=.01, le=1)
    people_counter_image_size: int = Field(default=640, ge=320, le=4096)
    people_counter_capture_interval: float = Field(default=5, ge=5, le=3600)
    people_counter_http_timeout: float = Field(default=40, ge=1, le=300)
    people_counter_nms_iou: float = Field(default=.5, ge=0, le=1)
    people_counter_regions_file: str = "person_counter/glass_region.json"
    people_counter_machine_areas_file: str = "person_counter/machine_areas.json"
    people_counter_command_priority: int = Field(default=10, ge=1)

    def to_settings(self) -> Settings:
        # 相对路径固定基于复制目录，而不是机器人启动时的工作目录。
        return Settings(
            camera=Camera(self.people_counter_device_serial, self.people_counter_channel_no),
            app_key=self.people_counter_app_key.get_secret_value(),
            app_secret=self.people_counter_app_secret.get_secret_value(),
            access_token=self.people_counter_access_token.get_secret_value(),
            model_path=BUNDLE_ROOT / self.people_counter_model_path,
            threads=self.people_counter_threads,
            confidence=self.people_counter_confidence,
            image_size=self.people_counter_image_size,
            capture_interval=self.people_counter_capture_interval,
            timeout=self.people_counter_http_timeout,
            nms_iou=self.people_counter_nms_iou,
            exclusion_regions=ExclusionRegions.load(BUNDLE_ROOT / self.people_counter_regions_file)
                if self.people_counter_regions_file else None,
            machine_areas=MachineAreas.load(BUNDLE_ROOT / self.people_counter_machine_areas_file)
                if self.people_counter_machine_areas_file else None,
        )


def create_service() -> PeopleCounter:
    """须在 nonebot.init() 后调用一次，复用返回的服务实例。"""
    from nonebot import get_plugin_config
    return PeopleCounter(get_plugin_config(Config).to_settings())

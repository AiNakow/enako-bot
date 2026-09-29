"""独立的萤石抓拍人数统计服务。"""
from .service import Camera, PeopleCounter, CounterError, Settings
from .machine_areas import MachineAreas

__all__ = ["Camera", "PeopleCounter", "CounterError", "Settings", "MachineAreas"]

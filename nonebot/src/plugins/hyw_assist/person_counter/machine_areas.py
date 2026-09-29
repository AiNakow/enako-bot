"""按人物框与固定游玩区域的重合比例统计每台机器的上机人数。"""
from dataclasses import dataclass
import json
import math
from pathlib import Path

from .capture import CounterError
from .regions import area, intersection_area


@dataclass(frozen=True)
class MachineArea:
    name: str
    max_people: int
    polygon: tuple


@dataclass(frozen=True)
class MachineAreas:
    reference_size: tuple
    overlap_threshold: float
    machines: tuple[MachineArea, ...]

    @classmethod
    def load(cls, path: Path):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8-sig"))
            size = tuple(cfg["reference_size"])
            threshold = float(cfg["overlap_threshold"])
            machines = tuple(MachineArea(
                str(item["name"]), int(item["max_people"]),
                tuple(tuple(float(v) for v in point) for point in item["polygon"]),
            ) for item in cfg["machines"])
            if len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
                raise ValueError
            if not math.isfinite(threshold) or not 0 < threshold <= 1 or not machines:
                raise ValueError
            if len({machine.name for machine in machines}) != len(machines):
                raise ValueError
            for machine in machines:
                if not machine.name or machine.max_people < 1 or len(machine.polygon) < 3:
                    raise ValueError
                if area(machine.polygon) <= 0 or any(
                    len(point) != 2 or any(not math.isfinite(value) or not 0 <= value <= size[i]
                                           for i, value in enumerate(point))
                    for point in machine.polygon
                ):
                    raise ValueError
            return cls(size, threshold, machines)
        except (OSError, ValueError, KeyError, TypeError):
            raise CounterError("游玩区域配置无效。") from None

    def scaled_polygon(self, machine: MachineArea, size):
        width, height = size
        ref_width, ref_height = self.reference_size
        if abs((width / height) / (ref_width / ref_height) - 1) > .01:
            raise CounterError("图片宽高比与游玩区域标定图不一致，请重新标定。")
        return tuple((x * width / ref_width, y * height / ref_height)
                     for x, y in machine.polygon)

    def overlaps(self, box, size):
        box_area = (box[2] - box[0]) * (box[3] - box[1])
        if box_area <= 0:
            raise CounterError("检测框面积无效。")
        return {
            machine.name: intersection_area(self.scaled_polygon(machine, size), box) / box_area
            for machine in self.machines
        }

    def count(self, detections, size):
        counts = {machine.name: 0 for machine in self.machines}
        limits = {machine.name: machine.max_people for machine in self.machines}
        for detection in detections:
            if detection["excluded"]:
                continue
            overlaps = self.overlaps(detection["box"], size)
            name, overlap = max(overlaps.items(), key=lambda item: item[1])
            if overlap >= self.overlap_threshold:
                counts[name] = min(counts[name] + 1, limits[name])
        return counts

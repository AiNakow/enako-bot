"""基于检测框覆盖比例的区域后处理，不修改模型输入图像。"""
from dataclasses import dataclass
import json
import math
from pathlib import Path

from .capture import CounterError


def area(points):
    return abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(points, points[1:] + points[:1]))) / 2


def intersection_area(polygon, box):
    """Sutherland–Hodgman：用轴对齐矩形逐边裁剪多边形。"""
    points = list(polygon)
    for axis, edge, sign in [(0, box[0], 1), (0, box[2], -1),
                             (1, box[1], 1), (1, box[3], -1)]:
        output = []
        for previous, current in zip(points[-1:] + points[:-1], points):
            inside_previous = sign * (previous[axis] - edge) >= 0
            inside_current = sign * (current[axis] - edge) >= 0
            if inside_previous != inside_current:
                ratio = (edge - previous[axis]) / (current[axis] - previous[axis])
                output.append(tuple(previous[i] + ratio * (current[i] - previous[i]) for i in (0, 1)))
            if inside_current:
                output.append(current)
        points = output
    return area(points)


@dataclass(frozen=True)
class ExclusionRegions:
    reference_size: tuple
    polygons: tuple
    overlap_threshold: float

    @classmethod
    def load(cls, path: Path):
        try:
            cfg = json.loads(path.read_text(encoding="utf-8-sig"))
            size = tuple(cfg["reference_size"])
            threshold = float(cfg["overlap_threshold"])
            polygons = tuple(tuple(tuple(float(v) for v in point) for point in poly)
                             for poly in cfg["polygons"])
            if len(size) != 2 or any(type(v) is not int or v <= 0 for v in size):
                raise ValueError
            if not math.isfinite(threshold) or not 0 < threshold <= 1 or not polygons:
                raise ValueError
            for poly in polygons:
                if len(poly) < 3 or any(len(p) != 2 for p in poly):
                    raise ValueError
                if any(not math.isfinite(v) or not 0 <= v <= size[i] for p in poly for i, v in enumerate(p)):
                    raise ValueError
                # 限制为有序凸多边形，避免自交/凹形区域产生不明确面积。
                crosses = [(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0])
                           for a, b, c in zip(poly, poly[1:]+poly[:1], poly[2:]+poly[:2])]
                if area(poly) <= 0 or not (all(v > 0 for v in crosses) or all(v < 0 for v in crosses)):
                    raise ValueError
                for a, b in zip(poly, poly[1:] + poly[:1]):
                    sides = [(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]) for p in poly]
                    if min(sides) < -1e-8 and max(sides) > 1e-8:
                        raise ValueError
            return cls(size, polygons, threshold)
        except (OSError, ValueError, KeyError, TypeError):
            raise CounterError("排除区域配置无效；需参考尺寸、0..1 阈值和顺序排列的凸多边形。") from None

    def scaled(self, size):
        width, height = size
        rw, rh = self.reference_size
        if abs((width / height) / (rw / rh) - 1) > .01:
            raise CounterError("图片宽高比与玻璃标定图不一致，请重新标定，避免错误过滤。")
        return [[(x * width / rw, y * height / rh) for x, y in poly] for poly in self.polygons]

    def overlap(self, box, size):
        polygons = self.scaled(size)
        x1, y1, x2, y2 = box
        box_area = (x2 - x1) * (y2 - y1)
        if box_area <= 0:
            raise CounterError("检测框面积无效。")
        return max(intersection_area(poly, box) / box_area for poly in polygons)

    def excludes(self, box, size):
        return self.overlap(box, size) >= self.overlap_threshold

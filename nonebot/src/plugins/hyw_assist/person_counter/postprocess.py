"""共享后处理：无效框过滤、玻璃区域排除、按置信度执行人物 NMS。"""
import math

from .capture import CounterError


def box_iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    total = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / total if total > 0 else 0.0


def process_detections(boxes, labels, scores, size, confidence, regions=None, nms_iou=.5):
    if not len(boxes) == len(labels) == len(scores):
        raise CounterError("检测框、类别和置信度数量不一致。")
    if regions:
        regions.scaled(size)
    width, height = size
    detections = []
    for index, (box, label, score) in enumerate(zip(boxes, labels, scores), 1):
        if len(box) != 4 or not all(math.isfinite(v) for v in (*box, label, score)):
            raise CounterError("模型返回了无效检测数据。")
        if int(label) != 0 or score < confidence:
            continue
        # 裁到实际图像范围，零面积框不参与人数统计。
        clipped = [max(0, min(width, box[0])), max(0, min(height, box[1])),
                   max(0, min(width, box[2])), max(0, min(height, box[3]))]
        invalid = clipped[2] <= clipped[0] or clipped[3] <= clipped[1]
        overlap = regions.overlap(clipped, size) if regions and not invalid else 0.0
        reason = "invalid" if invalid else "glass" if regions and overlap >= regions.overlap_threshold else "keep"
        detections.append({"id": index, "box": clipped, "confidence": float(score),
                           "glass_overlap": overlap, "reason": reason,
                           "excluded": reason != "keep", "duplicate_of": None, "duplicate_iou": None})
    # 先移除玻璃框，以免被排除的高置信度目标压制室内目标。
    candidates = sorted((d for d in detections if not d["excluded"]),
                        key=lambda d: (-d["confidence"], d["id"]))
    kept = []
    for detection in candidates:
        for previous in kept if nms_iou > 0 else ():
            overlap = box_iou(detection["box"], previous["box"])
            if overlap >= nms_iou:
                detection.update(reason="duplicate", excluded=True,
                                 duplicate_of=previous["id"], duplicate_iou=overlap)
                break
        if not detection["excluded"]:
            kept.append(detection)
    return detections

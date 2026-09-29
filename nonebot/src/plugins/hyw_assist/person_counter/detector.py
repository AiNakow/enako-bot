"""YOLO26n ONNX：RGB letterbox 输入，输出原图坐标的检测结果。"""
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image


def resize_bilinear(pixels: np.ndarray, width: int, height: int) -> np.ndarray:
    """半像素对齐的双线性缩放，不依赖 OpenCV，不附加降采样抗锯齿。"""
    source_h, source_w = pixels.shape[:2]
    x = np.clip((np.arange(width) + .5) * source_w / width - .5, 0, source_w - 1)
    y = np.clip((np.arange(height) + .5) * source_h / height - .5, 0, source_h - 1)
    x0, y0 = x.astype(int), y.astype(int)
    x1, y1 = np.minimum(x0 + 1, source_w - 1), np.minimum(y0 + 1, source_h - 1)
    wx, wy = (x - x0)[None, :, None], (y - y0)[:, None, None]
    top = pixels[y0[:, None], x0] * (1 - wx) + pixels[y0[:, None], x1] * wx
    bottom = pixels[y1[:, None], x0] * (1 - wx) + pixels[y1[:, None], x1] * wx
    return np.rint(top * (1 - wy) + bottom * wy).astype(np.uint8)


def preprocess(image: Image.Image, image_size: int):
    width, height = image.size
    scale = image_size / max(width, height)
    resized_w, resized_h = round(width * scale), round(height * scale)
    pixels = resize_bilinear(np.asarray(image.convert("RGB")), resized_w, resized_h)
    # 与原服务一致：短边补到 32 倍数，而不是强制补成正方形。
    pad_w, pad_h = (image_size - resized_w) % 32, (image_size - resized_h) % 32
    left, top = round(pad_w / 2 - .1), round(pad_h / 2 - .1)
    pixels = np.pad(pixels, ((top, pad_h-top), (left, pad_w-left), (0, 0)), constant_values=114)
    tensor = np.ascontiguousarray(pixels.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, scale, (left, top)


class OnnxDetector:
    """解码随包提供的 FP32 YOLO26n 原始检测头。"""

    def __init__(self, path: Path, image_size: int, threads: int):
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(path), sess_options=options,
                                            providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.image_size = image_size

    def predict(self, image: Image.Image, confidence: float):
        tensor, scale, (left, top) = preprocess(image, self.image_size)
        # 导出契约：[batch, 84, anchors]：中心坐标、宽高、80 类概率。
        rows = self.session.run(None, {self.input_name: tensor})[0][0].T
        labels = rows[:, 4:].argmax(axis=1)
        keep = (labels == 0) & (rows[:, 4] >= confidence)
        rows, labels = rows[keep], labels[keep]
        boxes = np.concatenate((rows[:, :2] - rows[:, 2:4] / 2,
                                rows[:, :2] + rows[:, 2:4] / 2), axis=1)
        # 原始检测头的候选框先做标准 NMS（IoU 0.7），再交给业务区域/去重处理。
        # 两次阈值不同的贪心 NMS 不能合并，否则低分候选可能重新进入最终计数。
        order = rows[:, 4].argsort()[::-1]
        selected = []
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        while order.size and len(selected) < 300:
            index = order[0]
            selected.append(index)
            others = order[1:]
            overlap = np.maximum(0, np.minimum(boxes[index, 2:], boxes[others, 2:])
                                 - np.maximum(boxes[index, :2], boxes[others, :2]))
            intersection = overlap.prod(axis=1)
            iou = intersection / (areas[index] + areas[others] - intersection)
            order = others[iou <= .7]
        boxes, rows, labels = boxes[selected], rows[selected], labels[selected]
        boxes -= np.array([left, top, left, top], dtype=np.float32)
        boxes /= scale
        return boxes.tolist(), labels.tolist(), rows[:, 4].tolist()

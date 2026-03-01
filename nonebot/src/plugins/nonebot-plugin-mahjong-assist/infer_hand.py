from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from .postprocess import (
    Det,
    area_xyxy,
    nms_dedup,
    select_best_hand_band,
    suppress_contained_boxes,
    to_tenhou_from_dets,
)

# -------- config --------
DEFAULT_IMG_SIZE = int(os.environ.get("IMG_SIZE", "640"))
DEFAULT_MAX_LONG_SIDE = int(os.environ.get("MAX_LONG_SIDE", "1280"))
DEFAULT_CONF_THR = float(os.environ.get("CONF_THR", "0.15"))
DEFAULT_NMS_IOU = float(os.environ.get("NMS_IOU", "0.6"))

DEFAULT_BAND = float(os.environ.get("BAND", "0.3"))
DEFAULT_BAND_PAD = float(os.environ.get("BAND_PAD", "0.02"))
DEFAULT_DEDUP_IOU = float(os.environ.get("DEDUP_IOU", "0.75"))
DEFAULT_CONTAIN_THR = float(os.environ.get("CONTAIN_THR", "0.85"))
DEFAULT_CONTAIN_AREA_RATIO = float(os.environ.get("CONTAIN_AREA_RATIO", "0.55"))


def _resize_long_side(img: np.ndarray, max_long_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    long_side = max(h, w)
    if long_side <= max_long_side:
        return img
    scale = max_long_side / float(long_side)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _letterbox(img: np.ndarray, new_shape: int = 640, color: Tuple[int, int, int] = (114, 114, 114)):
    """
    Resize and pad to square, return:
      img_lb, scale, pad_w, pad_h
    """
    h, w = img.shape[:2]
    r = min(new_shape / h, new_shape / w)
    new_unpad = (int(round(w * r)), int(round(h * r)))
    img_resized = cv2.resize(img, new_unpad, interpolation=cv2.INTER_LINEAR)

    dw = new_shape - new_unpad[0]
    dh = new_shape - new_unpad[1]
    dw /= 2
    dh /= 2

    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    img_padded = cv2.copyMakeBorder(img_resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img_padded, r, left, top


def _xywh_to_xyxy(xywh: np.ndarray) -> np.ndarray:
    x, y, w, h = xywh.T
    x1 = x - w / 2
    y1 = y - h / 2
    x2 = x + w / 2
    y2 = y + h / 2
    return np.stack([x1, y1, x2, y2], axis=1)


def _nms_xyxy(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> List[int]:
    if boxes.shape[0] == 0:
        return []
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)

        inds = np.where(ovr < iou_thr)[0]
        order = order[inds + 1]
    return keep


def _decode_ultralytics_onnx(pred: np.ndarray, conf_thr: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Supports common Ultralytics YOLOv8 ONNX output:
      pred shape: (1, 4+nc, n)
    Returns:
      boxes_xywh (N,4) in letterboxed image pixels
      cls_ids (N,)
      scores (N,)
    """
    if pred.ndim != 3 or pred.shape[0] != 1:
        raise ValueError(f"Unexpected pred shape: {pred.shape}")

    p = pred[0]  # (C, N)
    if p.shape[0] < 6:
        raise ValueError(f"Unexpected channels: {p.shape}")

    boxes = p[0:4, :].T  # (N,4)
    cls_scores = p[4:, :].T  # (N,nc)

    cls_ids = np.argmax(cls_scores, axis=1)
    scores = cls_scores[np.arange(cls_scores.shape[0]), cls_ids]

    mask = scores >= conf_thr
    return boxes[mask], cls_ids[mask], scores[mask]


class MahjongONNXRuntime:
    """
    Usage:
        rt = MahjongONNXRuntime("models/best.onnx", "models/names.json")
        out = rt.predict_bytes(image_bytes)
    """

    def __init__(
        self,
        model_path: str | Path,
        names_path: str | Path,
        *,
        imgsz: int = DEFAULT_IMG_SIZE,
        max_long_side: int = DEFAULT_MAX_LONG_SIDE,
        conf: float = DEFAULT_CONF_THR,
        nms_iou: float = DEFAULT_NMS_IOU,
        # hand filtering / dedup
        band: float = DEFAULT_BAND,
        band_pad: float = DEFAULT_BAND_PAD,
        contain_thr: float = DEFAULT_CONTAIN_THR,
        contain_area_ratio: float = DEFAULT_CONTAIN_AREA_RATIO,
        dedup_iou: float = DEFAULT_DEDUP_IOU,
        ort_intra_threads: int = 1,
        ort_inter_threads: int = 1,
    ):
        self.imgsz = int(imgsz)
        self.max_long_side = int(max_long_side)
        self.conf = float(conf)
        self.nms_iou = float(nms_iou)

        self.band = float(band)
        self.band_pad = float(band_pad)
        self.contain_thr = float(contain_thr)
        self.contain_area_ratio = float(contain_area_ratio)
        self.dedup_iou = float(dedup_iou)

        self.names = json.loads(Path(names_path).read_text(encoding="utf-8"))

        so = ort.SessionOptions()
        so.intra_op_num_threads = int(ort_intra_threads)
        so.inter_op_num_threads = int(ort_inter_threads)
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(str(model_path), sess_options=so, providers=["CPUExecutionProvider"])

        self.input_name = self.sess.get_inputs()[0].name
        self.output_name = self.sess.get_outputs()[0].name

    def predict_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        img_arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError("Failed to decode image bytes.")

        img_bgr = _resize_long_side(img_bgr, self.max_long_side)
        orig_h, orig_w = img_bgr.shape[:2]

        # letterbox
        img_lb, r, padw, padh = _letterbox(img_bgr, self.imgsz)

        # preprocess
        img_rgb = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        x = img_rgb.astype(np.float32) / 255.0
        x = np.transpose(x, (2, 0, 1))[None, ...]  # (1,3,H,W)

        # infer
        pred = self.sess.run([self.output_name], {self.input_name: x})[0]

        # decode
        boxes_xywh, cls_ids, scores = _decode_ultralytics_onnx(pred, self.conf)
        if boxes_xywh.shape[0] == 0:
            return {"tenhou": "", "num_tiles": 0, "detections": [], "orig_hw": [orig_h, orig_w], "imgsz": self.imgsz}

        boxes_xyxy = _xywh_to_xyxy(boxes_xywh)
        keep = _nms_xyxy(boxes_xyxy, scores, self.nms_iou)
        boxes_xyxy = boxes_xyxy[keep]
        cls_ids = cls_ids[keep]
        scores = scores[keep]

        dets: List[Det] = []
        for box, cid, sc in zip(boxes_xyxy, cls_ids, scores):
            x1, y1, x2, y2 = box.tolist()

            # undo letterbox
            x1 = (x1 - padw) / r
            x2 = (x2 - padw) / r
            y1 = (y1 - padh) / r
            y2 = (y2 - padh) / r

            # clip
            x1 = max(0.0, min(x1, orig_w))
            x2 = max(0.0, min(x2, orig_w))
            y1 = max(0.0, min(y1, orig_h))
            y2 = max(0.0, min(y2, orig_h))

            xc = ((x1 + x2) / 2.0) / max(1.0, orig_w)
            yc = ((y1 + y2) / 2.0) / max(1.0, orig_h)

            cls_name = self.names[int(cid)] if int(cid) < len(self.names) else str(int(cid))
            a = area_xyxy((x1, y1, x2, y2))

            dets.append(
                Det(
                    cls_id=int(cid),
                    cls_name=cls_name,
                    conf=float(sc),
                    xyxy=(float(x1), float(y1), float(x2), float(y2)),
                    x_center=float(xc),
                    y_center=float(yc),
                    area=float(a),
                )
            )

        # hand band + dedup
        hand = select_best_hand_band(dets, band=self.band, pad=self.band_pad)
        hand = suppress_contained_boxes(hand, contain_thr=self.contain_thr, area_ratio_thr=self.contain_area_ratio)
        hand = nms_dedup(hand, iou_thr=self.dedup_iou, class_aware=False)

        tenhou = to_tenhou_from_dets(hand)
        hand_sorted = sorted(hand, key=lambda d: d.x_center)

        return {
            "tenhou": tenhou,
            "num_tiles": len(hand_sorted),
            "detections": [
                {"cls": d.cls_name, "conf": d.conf, "xyxy": [*d.xyxy], "x_center": d.x_center, "y_center": d.y_center}
                for d in hand_sorted
            ],
            "orig_hw": [orig_h, orig_w],
            "imgsz": self.imgsz,
        }


if __name__ == "__main__":
    # quick local test
    import sys

    if len(sys.argv) < 4:
        print("Usage: python infer.py models/best.onnx models/names.json path/to/image.jpg")
        raise SystemExit(2)

    model_path, names_path, img_path = sys.argv[1], sys.argv[2], sys.argv[3]
    rt = MahjongONNXRuntime(model_path, names_path, imgsz=640, ort_intra_threads=1, ort_inter_threads=1)

    with open(img_path, "rb") as f:
        b = f.read()
    out = rt.predict_bytes(b)
    print(json.dumps(out, ensure_ascii=False, indent=2))
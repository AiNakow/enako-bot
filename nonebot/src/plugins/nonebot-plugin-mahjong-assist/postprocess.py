from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class Det:
    cls_id: int
    cls_name: str
    conf: float
    xyxy: Tuple[float, float, float, float]  # absolute pixels (x1,y1,x2,y2)
    x_center: float  # normalized 0..1
    y_center: float  # normalized 0..1
    area: float


# -------- tenhou mapping --------
def label_to_tenhou_token(name: str) -> Optional[str]:
    name = name.strip()
    if len(name) != 2:
        return None
    d, suit = name[0], name[1]
    if suit not in ("m", "p", "s", "z"):
        return None
    if not d.isdigit():
        return None
    if suit == "z":
        return (d + "z") if d in "1234567" else None
    return (d + suit) if d in "0123456789" else None


def tokens_to_tenhou_string(tokens: List[str]) -> str:
    if not tokens:
        return ""
    out = []
    run_digits = ""
    run_suit = None
    for t in tokens:
        d, s = t[0], t[1]
        if run_suit is None:
            run_suit = s
            run_digits = d
        elif s == run_suit:
            run_digits += d
        else:
            out.append(run_digits + run_suit)
            run_suit = s
            run_digits = d
    out.append(run_digits + run_suit)
    return "".join(out)


# -------- geometry helpers --------
def area_xyxy(a: Tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = a
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def intersection_area(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    return iw * ih


def iou_xyxy(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    inter = intersection_area(a, b)
    if inter <= 0:
        return 0.0
    ua = area_xyxy(a) + area_xyxy(b) - inter
    return inter / ua if ua > 0 else 0.0


def containment_ratio(inner: Tuple[float, float, float, float], outer: Tuple[float, float, float, float]) -> float:
    inner_a = area_xyxy(inner)
    if inner_a <= 0:
        return 0.0
    return intersection_area(inner, outer) / inner_a


# -------- dedup and band selection --------
def suppress_contained_boxes(
    dets: List[Det],
    contain_thr: float = 0.85,
    area_ratio_thr: float = 0.55,
) -> List[Det]:
    if not dets:
        return []
    dets_sorted = sorted(dets, key=lambda d: d.area, reverse=True)  # big first
    suppressed = [False] * len(dets_sorted)

    for i in range(len(dets_sorted)):
        if suppressed[i]:
            continue
        big = dets_sorted[i]
        for j in range(i + 1, len(dets_sorted)):
            if suppressed[j]:
                continue
            small = dets_sorted[j]
            if small.area <= 0 or big.area <= 0:
                continue
            if (small.area / big.area) > area_ratio_thr:
                continue
            if containment_ratio(small.xyxy, big.xyxy) >= contain_thr:
                suppressed[j] = True

    return [d for d, s in zip(dets_sorted, suppressed) if not s]


def nms_dedup(
    dets: List[Det],
    iou_thr: float = 0.75,
    class_aware: bool = False,
) -> List[Det]:
    if not dets:
        return []
    dets_sorted = sorted(dets, key=lambda d: d.conf, reverse=True)
    keep: List[Det] = []
    for d in dets_sorted:
        ok = True
        for k in keep:
            if class_aware and d.cls_id != k.cls_id:
                continue
            if iou_xyxy(d.xyxy, k.xyxy) >= iou_thr:
                ok = False
                break
        if ok:
            keep.append(d)
    return keep


def select_best_hand_band(
    dets: List[Det],
    band: float = 0.18,
    pad: float = 0.02,
    step: float = 0.01,
    w_wide: float = 0.60,
    w_lower: float = 0.10,
    w_flat: float = 0.80,  # reward flatter (smaller std_y)
) -> List[Det]:
    if not dets:
        return []
    ys = np.array([d.y_center for d in dets], dtype=np.float32)

    best_score = -1e9
    best_y0 = 0.0

    y0 = 0.0
    while y0 <= 1.0:
        y1 = y0 + band
        idx = np.where((ys >= y0) & (ys <= y1))[0]
        if idx.size == 0:
            y0 += step
            continue

        inband = [dets[i] for i in idx.tolist()]
        sum_conf = float(sum(d.conf for d in inband))
        xs = [d.x_center for d in inband]
        xspan = (max(xs) - min(xs)) if len(xs) >= 2 else 0.0
        std_y = float(np.std([d.y_center for d in inband])) if len(inband) >= 2 else 0.0
        y_mid = (y0 + y1) / 2.0

        score = sum_conf + w_wide * xspan + w_lower * y_mid - w_flat * std_y
        if score > best_score:
            best_score = score
            best_y0 = y0
        y0 += step

    y0 = max(0.0, best_y0 - pad)
    y1 = min(1.0, best_y0 + band + pad)
    return [d for d in dets if y0 <= d.y_center <= y1]


def to_tenhou_from_dets(dets: List[Det]) -> str:
    dets_sorted = sorted(dets, key=lambda d: d.x_center)
    tokens: List[str] = []
    for d in dets_sorted:
        tok = label_to_tenhou_token(d.cls_name)
        if tok:
            tokens.append(tok)
    return tokens_to_tenhou_string(tokens)
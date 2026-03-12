import numpy as np

MAX_SCORE = 100.0

PENALTY = {
    "moldy": 30,
    "pest_damage": 7,
    "shriveled": 7,
    "broken": 5,
}
ALLOWED_DEFECTS = set(PENALTY.keys())


def _to_numpy(x):
    if hasattr(x, 'cpu'):
        return x.cpu().numpy()
    return x


def score_from_defects(defect_labels) -> float:
    s = MAX_SCORE
    for d in defect_labels:
        s -= PENALTY.get(d, 0)
    return max(s, 0.0)


def classify_grade(score: float) -> str:
    score = max(0.0, min(float(score), 100.0))
    if score == 100.0:
        return "Extra Class"
    if 92 <= score < 100.0:
        return "Class I"
    if 85 <= score < 92:
        return "Class II"
    return "Non-trade"


def price_per_kg_from_score(score: float, max_price_per_kg: float) -> float:
    score = max(0.0, min(float(score), 100.0))
    grade = classify_grade(score)
    if grade == "Non-trade":
        return 0.0
    mp = max(1.0, float(max_price_per_kg))
    return round((score / 100.0) * mp, 2)


def get_defect_boxes(result, conf_min=0.25, label_map=None, kernel_label="peanut_kernel"):
    label_map = label_map or {}
    defects = []
    kernel_label = str(kernel_label).strip().lower()

    if result is None or result.boxes is None or len(result.boxes) == 0:
        return defects

    cls_ids = _to_numpy(result.boxes.cls).astype(int).flatten()
    confs = _to_numpy(result.boxes.conf).flatten()
    xyxy = _to_numpy(result.boxes.xyxy)
    names = result.names

    for cid, conf, box in zip(cls_ids, confs, xyxy):
        if float(conf) < conf_min:
            continue
        raw = str(names.get(int(cid), "")).strip().lower()
        label = str(label_map.get(raw, raw)).strip().lower()
        if label == kernel_label:
            continue
        if label not in ALLOWED_DEFECTS:
            continue
        defects.append({
            "label": label,
            "box": tuple(map(float, box)),
            "conf": float(conf),
        })
    return defects


def get_kernel_boxes(result, conf_min=0.25, kernel_label="peanut_kernel"):
    boxes = []
    kernel_label = str(kernel_label).strip().lower()

    if result is None or result.boxes is None or len(result.boxes) == 0:
        return boxes

    cls_ids = _to_numpy(result.boxes.cls).astype(int).flatten()
    confs = _to_numpy(result.boxes.conf).flatten()
    xyxy = _to_numpy(result.boxes.xyxy)
    names = result.names

    for cid, conf, box in zip(cls_ids, confs, xyxy):
        if float(conf) < conf_min:
            continue
        label = str(names.get(int(cid), "")).strip().lower()
        if label == kernel_label:
            boxes.append(tuple(map(float, box)))
    return boxes


def assign_defects_to_kernels(kernel_boxes, defects, max_distance_px=None):
    per_kernel = [set() for _ in kernel_boxes]

    def center(box):
        x1, y1, x2, y2 = box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    for d in defects:
        cx, cy = center(d["box"])
        best_i = None
        best_dist_sq = float('inf')

        for i, (x1, y1, x2, y2) in enumerate(kernel_boxes):
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                best_i = i
                best_dist_sq = 0
                break
            kcx = (x1 + x2) / 2.0
            kcy = (y1 + y2) / 2.0
            dist_sq = (kcx - cx) ** 2 + (kcy - cy) ** 2
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_i = i

        if best_i is not None:
            if max_distance_px is not None:
                if best_dist_sq > max_distance_px ** 2:
                    continue
            per_kernel[best_i].add(d["label"])
    return per_kernel


def compute_kernel_results(kernel_boxes, defects, max_price_per_kg: float, max_distance_px: float = None):
    kernel_defects = assign_defects_to_kernels(kernel_boxes, defects, max_distance_px)
    max_price_per_kg = max(1.0, float(max_price_per_kg))

    kernel_results = []
    for box, defs in zip(kernel_boxes, kernel_defects):
        score = score_from_defects(defs)
        grade = classify_grade(score)
        ppk = price_per_kg_from_score(score, max_price_per_kg=max_price_per_kg)
        kernel_results.append({
            "box": box,
            "defects": sorted(list(defs)),
            "score": round(float(score), 2),
            "grade": grade,
            "price_per_kg": ppk,
        })

    detected_n = len(kernel_results)
    if detected_n == 0:
        tray_avg_score = 0.0
    else:
        total_score = sum(k["score"] for k in kernel_results)
        tray_avg_score = total_score / float(detected_n)

    tray_avg_score = round(tray_avg_score, 2)
    tray_grade = classify_grade(tray_avg_score)
    tray_price_per_kg = price_per_kg_from_score(tray_avg_score, max_price_per_kg=max_price_per_kg)

    return kernel_results, tray_avg_score, tray_grade, tray_price_per_kg
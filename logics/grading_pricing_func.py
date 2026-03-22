#logics/grading_pricing_func.py
import numpy as np

''''
| Defect             | Score | Grade     |
| ------------------ | ----- | --------- |
| broken             | 92    | Class I   |
| shriveled          | 88    | Class I   |
| pest_damage        | 85    | Class I   |
| broken + shriveled | 80    | Class I   |
| shriveled + pest   | 73    | Class II  |
| pest + broken      | 77    | Class II  |
| moldy              | 70    | Non-trade |
'''

MAX_SCORE = 100.0

PENALTY = {
    "damage": 30,
    "shriveled": 12,
    "broken": 9,
}
ALLOWED_DEFECTS = set(PENALTY.keys())   # normal is not a defect

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
    if 80 <= score < 100.0:
        return "Class I"
    if 73 <= score < 80:
        return "Class II"
    return "Non-trade"

def price_per_kg_from_score(score: float, max_price_per_kg: float) -> float:
    score = max(0.0, min(float(score), 100.0))
    grade = classify_grade(score)
    if grade == "Non-trade":
        return 0.0
    mp = max(1.0, float(max_price_per_kg))
    return round((score / 100.0) * mp, 2)


# ----- Box extraction helpers (for preview and offline) -----
def get_defect_boxes(result, conf_min=0.25, label_map=None, kernel_label="normal"):
    label_map = label_map or {}
    defects = []
    kernel_label = str(kernel_label).strip().lower()

    if result is None or result.boxes is None or len(result.boxes.xyxy) == 0:
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
        if label == kernel_label:          # skip normal kernels
            continue
        if label not in ALLOWED_DEFECTS:   # also skip any unexpected labels
            continue
        defects.append({
            "label": label,
            "box": tuple(map(float, box)),
            "conf": float(conf),
        })
    return defects

def get_kernel_boxes(result, conf_min=0.25, kernel_label="normal"):
    boxes = []
    kernel_label = str(kernel_label).strip().lower()

    if result is None or result.boxes is None or len(result.boxes.xyxy) == 0:
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


# ----- Assignment to contours (core pipeline) -----
def assign_boxes_to_contours(contours, detections):
    """
    contours: list of dicts with key 'box' [x1,y1,x2,y2] from detect_kernel_contours
    detections: DetectionResult object (with .boxes and .names)
    Returns list of kernel_data: [{'box': cbox, 'labels': [defect1, defect2, ...]}, ...]
    """
    kernel_data = []
    if not contours or not detections:
        return kernel_data

    boxes = detections.boxes.xyxy
    classes = detections.boxes.cls
    names = detections.names

    def center(b):
        return ((b[0]+b[2])/2, (b[1]+b[3])/2)

    for c in contours:
        cbox = c['box']   # [x1,y1,x2,y2]
        cx1, cy1, cx2, cy2 = cbox
        any_box_inside = False
        defect_labels = set()

        for box, cls_id in zip(boxes, classes):
            cx, cy = center(box)
            if cx1 <= cx <= cx2 and cy1 <= cy <= cy2:
                any_box_inside = True
                label = names.get(int(cls_id), "").strip().lower()
                if label in ALLOWED_DEFECTS:
                    defect_labels.add(label)

        # A contour is a kernel iff it contains at least one detection (any class)
        if any_box_inside:
            kernel_data.append({
                "box": cbox,
                "labels": list(defect_labels)
            })

    return kernel_data


# ----- Compute results from kernel_data -----
def compute_kernel_results_from_contours(kernel_data, max_price_per_kg):
    kernel_results = []
    for k in kernel_data:
        defects = k["labels"]   # already unique
        score = score_from_defects(defects)
        grade = classify_grade(score)
        price = price_per_kg_from_score(score, max_price_per_kg)
        kernel_results.append({
            "box": k["box"],
            "defects": defects,
            "score": round(score, 2),
            "grade": grade,
            "price_per_kg": price
        })

    if not kernel_results:
        tray_avg = 0.0
    else:
        tray_avg = sum(k["score"] for k in kernel_results) / len(kernel_results)

    tray_grade = classify_grade(tray_avg)
    tray_price = price_per_kg_from_score(tray_avg, max_price_per_kg)

    return kernel_results, tray_avg, tray_grade, tray_price


# ----- Preview helper (fast, using proximity) -----
def compute_kernel_results_from_boxes(kernel_boxes, defects, max_price_per_kg, max_distance_px=None):
    """
    For preview only: assign defects to kernel boxes by proximity (no contours).
    """
    assigned = assign_defects_to_kernels(kernel_boxes, defects, max_distance_px)
    kernel_data = []
    for i, box in enumerate(kernel_boxes):
        kernel_data.append({
            "box": box,
            "labels": list(assigned[i]) if i < len(assigned) else []
        })
    return compute_kernel_results_from_contours(kernel_data, max_price_per_kg)

def assign_defects_to_kernels(kernel_boxes, defects, max_distance_px=None):
    """Helper for preview: assign each defect to the nearest kernel box."""
    per_kernel = [set() for _ in kernel_boxes]

    def center(box):
        return ((box[0]+box[2])/2.0, (box[1]+box[3])/2.0)

    for d in defects:
        cx, cy = center(d["box"])
        best_i = None
        best_dist_sq = float('inf')
        for i, kbox in enumerate(kernel_boxes):
            kcx, kcy = center(kbox)
            dist_sq = (kcx - cx)**2 + (kcy - cy)**2
            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_i = i
        if best_i is not None:
            if max_distance_px is None or best_dist_sq <= max_distance_px**2:
                per_kernel[best_i].add(d["label"])
    return per_kernel
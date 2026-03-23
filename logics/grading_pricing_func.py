# logics/grading_pricing_func.py

import numpy as np
import cv2

MAX_SCORE = 100.0

PENALTY = {
    "damage": 30,
    "shriveled": 12,
    "broken": 9,
}

ALLOWED_DEFECTS = set(PENALTY.keys())  # normal is not a defect


def _to_numpy(x):
    if hasattr(x, 'cpu'):
        return x.cpu().numpy()
    return x


# -----------------------------
# SCORING FUNCTIONS
# -----------------------------

def score_from_defects(defect_labels) -> float:
    """Compute kernel score based on detected defects."""
    s = MAX_SCORE
    for d in set(defect_labels):  # prevent duplicates
        s -= PENALTY.get(d, 0)
    return max(s, 0.0)


def classify_grade(score: float) -> str:
    """Convert score into grade."""
    score = max(0.0, min(float(score), 100.0))

    if score == 100.0:
        return "Extra Class"

    if 80 <= score < 100:
        return "Class I"

    if 73 <= score < 80:
        return "Class II"

    return "Non-trade"


def price_per_kg_from_score(score: float, max_price_per_kg: float) -> float:
    """Compute price/kg from score."""
    score = max(0.0, min(float(score), 100.0))
    grade = classify_grade(score)

    if grade == "Non-trade":
        return 0.0

    mp = max(1.0, float(max_price_per_kg))
    return round((score / 100.0) * mp, 2)


# -----------------------------
# YOLO BOX EXTRACTION
# -----------------------------

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


# -----------------------------
# CONTOUR ASSIGNMENT
# -----------------------------

def assign_boxes_to_contours(contours, detections):

    kernel_data = []

    if not contours or not detections:
        return kernel_data

    boxes = detections.boxes.xyxy
    classes = detections.boxes.cls
    names = detections.names

    def center(b):
        return ((b[0]+b[2])/2, (b[1]+b[3])/2)

    for c in contours:

        cbox = c['box']
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

        if any_box_inside:

            kernel_data.append({
                "box": cbox,
                "labels": list(defect_labels)
            })

    return kernel_data


# -----------------------------
# YOLO + CONTOUR FUSION
# -----------------------------

def assign_boxes_to_contours_all_classes(contours, yolo_result):

    if yolo_result is None or yolo_result.boxes is None:
        return []

    boxes = yolo_result.boxes

    def to_numpy(arr):
        if hasattr(arr, 'cpu'):
            return arr.cpu().numpy()
        elif hasattr(arr, 'numpy'):
            return arr.numpy()
        else:
            return np.array(arr)

    xyxy = to_numpy(boxes.xyxy)
    confs = to_numpy(boxes.conf).flatten()
    cls = to_numpy(boxes.cls).flatten().astype(int)

    class_names = ['normal', 'damage', 'shriveled', 'broken']

    def class_name(idx):
        return class_names[int(idx)]

    kernel_list = []

    for cnt in contours:

        cnt_box = cnt['box']

        overlapping = []

        for box, conf, cls_idx in zip(xyxy, confs, cls):

            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2

            if cnt_box[0] <= cx <= cnt_box[2] and cnt_box[1] <= cy <= cnt_box[3]:
                overlapping.append((class_name(cls_idx), conf, box))

        if not overlapping:
            continue

        defect_types = set()
        max_conf = 0

        for cls_name, conf, _ in overlapping:

            max_conf = max(max_conf, conf)

            if cls_name != "normal":
                defect_types.add(cls_name)

        kernel_list.append({
            "box": cnt_box,
            "conf": max_conf,
            "defects": list(defect_types)
        })

    return kernel_list


# -----------------------------
# KERNEL RESULT COMPUTATION
# -----------------------------

def compute_kernel_results_from_kernel_data(kernel_data, max_price_per_kg=250.0):

    if not kernel_data:
        return [], 0.0, "No Detection", 0.0

    kernel_results = []
    total_score = 0.0
    count = 0

    for k in kernel_data:

        defects = k.get("defects", [])

        score = score_from_defects(defects)
        grade = classify_grade(score)
        price = price_per_kg_from_score(score, max_price_per_kg)

        kernel_results.append({
            "box": k["box"],
            "score": score,
            "grade": grade,
            "price_per_kg": price,
            "defects": defects
        })

        total_score += score
        count += 1

    tray_avg = total_score / count if count else 0.0
    tray_grade = classify_grade(tray_avg)
    price = price_per_kg_from_score(tray_avg, max_price_per_kg)

    return kernel_results, tray_avg, tray_grade, price


# -----------------------------
# PREVIEW HELPER
# -----------------------------

def assign_defects_to_kernels(kernel_boxes, defects, max_distance_px=None):

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
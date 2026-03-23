import numpy as np

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
# SCORING
# -----------------------------

def score_from_defects(defect_labels) -> float:
    s = MAX_SCORE
    labels = set()
    for d in defect_labels:
        if isinstance(d, dict):
            labels.add(d.get("label", "").lower())
        else:
            labels.add(str(d).lower())
    for label in labels:
        s -= PENALTY.get(label, 0)
    return max(s, 0.0)


def classify_grade(score: float) -> str:
    score = max(0.0, min(float(score), 100.0))
    if score == 100.0:
        return "Extra Class"
    if 80 <= score < 100:
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


# -----------------------------
# CONTOUR + YOLO FUSION
# -----------------------------

def assign_boxes_to_contours_all_classes(contours, yolo_result):
    if yolo_result is None or yolo_result.boxes is None:
        return []

    boxes = _to_numpy(yolo_result.boxes.xyxy)
    confs = _to_numpy(yolo_result.boxes.conf).flatten()
    cls_ids = _to_numpy(yolo_result.boxes.cls).flatten().astype(int)
    names = yolo_result.names
    class_names = ['broken','damage','normal', 'shriveled']

    kernel_list = []

    for cnt in contours:
        cnt_box = cnt['box']
        overlapping = []

        for box, conf, cls_idx in zip(boxes, confs, cls_ids):
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            if cnt_box[0] <= cx <= cnt_box[2] and cnt_box[1] <= cy <= cnt_box[3]:
                overlapping.append((class_names[int(cls_idx)], conf, box))

        if not overlapping:
            # no detections inside contour
            kernel_list.append({
                "box": cnt_box,
                "conf": 0.0,
                "defects": [{"box": cnt_box, "label": "normal"}],
                "has_normal": True
            })
            continue

        max_conf = max([conf for _, conf, _ in overlapping])
        defects = [{"box": box, "label": cls_name}
                   for cls_name, _, box in overlapping if cls_name != "normal"]
        has_normal = any(cls_name == "normal" for cls_name, _, _ in overlapping)

        # If no defects, mark as normal
        if has_normal and not defects:
            defects.append({"box": cnt_box, "label": "normal"})

        kernel_list.append({
            "box": cnt_box,
            "conf": max_conf,
            "defects": defects,
            "has_normal": has_normal
        })

    return kernel_list


# -----------------------------
# COMPUTE KERNEL RESULTS
# -----------------------------
def compute_kernel_results_from_kernel_data(kernel_data, max_price_per_kg=250.0):
    if not kernel_data:
        return [], 0.0, "No Detection", 0.0

    kernel_results = []
    total_score = 0.0
    count = 0

    for k in kernel_data:
        defects = k.get("defects", [])
        has_normal = k.get("has_normal", False)

        # Skip only if no defects AND no normal
        if not defects and not has_normal:
            continue

        # Compute score, grade, price
        if defects:
            score = score_from_defects([d["label"] for d in defects])
            grade = classify_grade(score)
            price = price_per_kg_from_score(score, max_price_per_kg)
        elif has_normal:
            score = 100.0
            grade = "Extra Class"
            price = max_price_per_kg
        else:
            # Should never reach here due to the continue above
            score = 0.0
            grade = "Non-trade"
            price = 0.0

        kernel_results.append({
            "box": k["box"],
            "score": score,
            "grade": grade,
            "price_per_kg": price,
            "defects": defects,
            "has_normal": has_normal,
            "max_price": max_price_per_kg
        })

        total_score += score
        count += 1

    tray_avg = total_score / count if count else 0.0
    tray_grade = classify_grade(tray_avg)
    tray_price = price_per_kg_from_score(tray_avg, max_price_per_kg)

    return kernel_results, tray_avg, tray_grade, tray_price
import cv2
import numpy as np

def find_kernel_boxes(frame_bgr):
    """
    Returns list of kernel boxes [(x1,y1,x2,y2), ...]
    This is a baseline contour method; you may tune thresholds for your tray/lighting.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (7, 7), 0)

    # Threshold: adjust depending on background/lighting
    # If your tray is dark and kernels are light, this usually works.
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Clean noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=2)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=2)

    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes = []
    H, W = frame_bgr.shape[:2]

    for c in cnts:
        area = cv2.contourArea(c)
        if area < 500:  # 👈 tune: ignore tiny blobs
            continue

        x, y, w, h = cv2.boundingRect(c)

        # filter weird skinny shapes (optional)
        if w < 10 or h < 10:
            continue

        x1, y1 = max(x, 0), max(y, 0)
        x2, y2 = min(x + w, W - 1), min(y + h, H - 1)
        boxes.append((x1, y1, x2, y2))

    # sort left->right top->bottom (optional)
    boxes.sort(key=lambda b: (b[1], b[0]))
    return boxes

def merge_kernel_boxes(contour_boxes, yolo_normal_boxes, iou_thresh=0.5):
    """
    Prefer YOLO 'normal' boxes when they overlap contour boxes.
    """
    def iou(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
        inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, inter_x2 - inter_x1), max(0, inter_y2 - inter_y1)
        inter = iw * ih
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0

    final_boxes = []

    for c in contour_boxes:
        replaced = False
        for y in yolo_normal_boxes:
            if iou(c, y) > iou_thresh:
                final_boxes.append(y)
                replaced = True
                break
        if not replaced:
            final_boxes.append(c)

    return final_boxes


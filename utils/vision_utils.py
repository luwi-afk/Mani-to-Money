import cv2
import numpy as np
import ncnn

def run_yolo(net, frame_bgr, imgsz=1280, conf_thresh=0.50, iou_thresh=0.45):
    h0, w0 = frame_bgr.shape[:2]

    # Letterbox resize to imgsz x imgsz
    r = imgsz / max(w0, h0)
    new_w = int(round(w0 * r))
    new_h = int(round(h0 * r))
    img = cv2.resize(frame_bgr, (new_w, new_h))
    dw = imgsz - new_w
    dh = imgsz - new_h
    top = dh // 2
    bottom = dh - top
    left = dw // 2
    right = dw - left
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114,114,114))

    # Inference
    mat = ncnn.Mat.from_pixels(img, ncnn.Mat.PixelType.PIXEL_BGR, imgsz, imgsz)
    mat.substract_mean_normalize([0, 0, 0], [1/255.0, 1/255.0, 1/255.0])
    ex = net.create_extractor()
    ex.input("in0", mat)
    ret, out = ex.extract("out0")
    if ret != 0:
        return None

    data = np.array(out).T   # shape (num_detections, num_classes+5)

    # Check if coordinates are normalized
    if data.size > 0:
        max_coord = np.max(data[:, :4])
        normalized = max_coord <= 1.1
    else:
        normalized = False

    detections = []
    for row in data:
        x1, y1, x2, y2 = row[0:4]
        if normalized:
            x1 *= imgsz
            y1 *= imgsz
            x2 *= imgsz
            y2 *= imgsz

        # Clip to padded image bounds
        x1 = np.clip(x1, 0, imgsz)
        y1 = np.clip(y1, 0, imgsz)
        x2 = np.clip(x2, 0, imgsz)
        y2 = np.clip(y2, 0, imgsz)

        # Skip if the box is completely outside the actual image area
        if (x2 <= left or x1 >= left + new_w or y2 <= top or y1 >= top + new_h):
            continue

        if x2 <= x1 or y2 <= y1:
            continue

        class_scores = 1.0 / (1.0 + np.exp(-row[4:]))
        max_score = np.max(class_scores)
        class_id = np.argmax(class_scores)
        if max_score >= conf_thresh:
            detections.append([x1, y1, x2, y2, max_score, class_id])

    if not detections:
        return np.empty((0, 6))

    boxes = np.array(detections)[:, :4]
    scores = np.array(detections)[:, 4]
    cls_ids = np.array(detections)[:, 5].astype(int)

    # Remove padding and scale to original image
    boxes[:, 0] -= left
    boxes[:, 1] -= top
    boxes[:, 2] -= left
    boxes[:, 3] -= top
    boxes[:, 0] /= r
    boxes[:, 1] /= r
    boxes[:, 2] /= r
    boxes[:, 3] /= r
    boxes[:, 0] = np.clip(boxes[:, 0], 0, w0)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, h0)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, w0)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, h0)

    valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
    boxes = boxes[valid]
    scores = scores[valid]
    cls_ids = cls_ids[valid]

    if len(boxes) == 0:
        return np.empty((0, 6))

    # NMS
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), conf_thresh, iou_thresh)
    if len(indices) == 0:
        return np.empty((0, 6))

    final = []
    for i in indices.flatten():
        final.append([boxes[i, 0], boxes[i, 1], boxes[i, 2], boxes[i, 3], scores[i], cls_ids[i]])
    return np.array(final)


def detect_kernel_contours(frame_bgr, target_size=1280):
    """
    Detect peanut kernels on a tray with holes.
    Works on any resolution by first resizing to target_size.
    Returns a list of dicts: {"box": [x1, y1, x2, y2], "area": area}
    (coordinates are in the original image space).
    """
    h0, w0 = frame_bgr.shape[:2]

    # Resize to target_size for consistent processing
    frame_resized = cv2.resize(frame_bgr, (target_size, target_size))

    # Convert to grayscale and apply mild blur
    gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive thresholding to handle uneven lighting
    thresh = cv2.adaptiveThreshold(blur, 255,
                                   cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV,
                                   15, 2)

    # Morphological closing to fill small holes
    kernel = np.ones((3, 3), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Opening to remove small specks
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel, iterations=1)

    # Find external contours
    contours, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Prepare to store valid kernel boxes (in resized coordinates)
    resized_boxes = []

    # Thresholds tuned for 1280 image
    min_area = 1600
    max_area = 12000

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue

        perimeter = cv2.arcLength(c, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < 0.5 or circularity > 0.95:
            continue

        x, y, w, h = cv2.boundingRect(c)
        aspect_ratio = w / float(h)
        if aspect_ratio < 0.5 or aspect_ratio > 2.0:
            continue

        resized_boxes.append({"box": [x, y, x + w, y + h], "area": area})

    # Scale boxes back to original image coordinates
    scale_x = w0 / target_size
    scale_y = h0 / target_size
    original_boxes = []
    for box in resized_boxes:
        x1, y1, x2, y2 = box["box"]
        original_boxes.append({
            "box": [x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y],
            "area": box["area"] * (scale_x * scale_y)   # area scaled
        })
    return original_boxes
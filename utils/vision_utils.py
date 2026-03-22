import cv2
import numpy as np
import ncnn

def run_yolo(net, frame_bgr, imgsz=640, conf_thresh=0.50, iou_thresh=0.45):
    h0, w0 = frame_bgr.shape[:2]
    print(f"Original frame: {h0} x {w0}")

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

    print(f"Letterbox: left={left}, top={top}, r={r:.4f}, new_w={new_w}, new_h={new_h}")

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

    # Show first 3 boxes after transformation
    if len(boxes) > 0:
        print("First 3 boxes after mapping:")
        for i in range(min(3, len(boxes))):
            print(f"  Box {i}: {boxes[i]}, score={scores[i]}, class={cls_ids[i]}")

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


def detect_kernel_contours(frame_bgr):
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_boxes = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 300:
            continue
        x, y, w, h = cv2.boundingRect(c)
        contour_boxes.append({"box": [x, y, x+w, y+h], "area": area})
    return contour_boxes
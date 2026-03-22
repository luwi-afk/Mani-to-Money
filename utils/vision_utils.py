import cv2
import numpy as np
import ncnn

def run_yolo(net, frame_bgr, imgsz=640, conf_thresh=0.5, iou_thresh=0.45):
    h0, w0 = frame_bgr.shape[:2]

    # Letterbox
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

    # out shape: (num_classes+4, num_detections) -> (num_detections, num_classes+4)
    data = np.array(out).T

    # Determine number of classes
    num_classes = data.shape[1] - 4

    # Format detection
    sample = data[:min(100, len(data))]
    x1, y1, x2, y2 = sample[:, 0], sample[:, 1], sample[:, 2], sample[:, 3]
    valid = (x1 < x2) & (y1 < y2)
    format_corners = np.mean(valid) > 0.5

    detections = []
    for row in data:
        if not format_corners:
            cx, cy, w, h = row[0:4]
            x1 = cx - w/2
            y1 = cy - h/2
            x2 = cx + w/2
            y2 = cy + h/2
        else:
            x1, y1, x2, y2 = row[0:4]

        # Normalize if needed
        if np.max([x1, y1, x2, y2]) <= 1.1:
            x1 *= imgsz
            y1 *= imgsz
            x2 *= imgsz
            y2 *= imgsz

        # Class scores – slice exactly num_classes entries after bbox
        class_scores = 1.0 / (1.0 + np.exp(-row[4:4+num_classes]))
        max_score = np.max(class_scores)
        class_id = np.argmax(class_scores)
        if max_score >= conf_thresh:
            detections.append([x1, y1, x2, y2, max_score, class_id])

    if not detections:
        return np.empty((0, 6))

    boxes = np.array(detections)[:, :4]
    scores = np.array(detections)[:, 4]
    cls_ids = np.array(detections)[:, 5].astype(int)

    # Remove padding and scale to original
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
import cv2
import numpy as np
import ncnn

def run_yolo(net, frame_bgr, imgsz=640, conf_thresh=0.25, iou_thresh=0.45):
    """
    Run NCNN inference with letterbox resizing.
    Returns numpy array of shape (N, 6): [x1, y1, x2, y2, confidence, class_id]
    Coordinates are in the original image space.
    """
    h0, w0 = frame_bgr.shape[:2]          # original dimensions

    # 1. Letterbox resize to imgsz x imgsz
    r = imgsz / max(w0, h0)               # scale factor to fit within imgsz
    new_w = int(round(w0 * r))
    new_h = int(round(h0 * r))
    img = cv2.resize(frame_bgr, (new_w, new_h))
    # Compute padding
    dw = imgsz - new_w
    dh = imgsz - new_h
    top = dh // 2
    bottom = dh - top
    left = dw // 2
    right = dw - left
    # Add padding (gray)
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114,114,114))

    # 2. Convert to ncnn Mat and run inference
    mat = ncnn.Mat.from_pixels(img, ncnn.Mat.PixelType.PIXEL_BGR, imgsz, imgsz)
    mat.substract_mean_normalize([0, 0, 0], [1/255.0, 1/255.0, 1/255.0])
    ex = net.create_extractor()
    ex.input("in0", mat)
    ret, out = ex.extract("out0")
    if ret != 0:
        return None

    # out shape: (num_classes+5, num_detections) -> transpose to (num_detections, num_classes+5)
    data = np.array(out).T                # shape (num_detections, 9) for 5 classes

    # Number of detections and grid information
    num_detections = data.shape[0]        # e.g., 8400 for 640, 33600 for 1280
    # For YOLOv5/v8, the detections are arranged in three grids: stride 8, 16, 32.
    # We compute the grid sizes from the input size.
    strides = [8, 16, 32]
    grid_sizes = [imgsz // s for s in strides]   # e.g., [160, 80, 40] for 1280
    cells_per_grid = [gs * gs for gs in grid_sizes]
    total_cells = sum(cells_per_grid)
    if total_cells != num_detections:
        # Fallback: assume output is in order of stride8, stride16, stride32
        # (should match training export)
        pass

    # Split the data into the three grids
    offset = 0
    detections_list = []
    for stride, gs, cells in zip(strides, grid_sizes, cells_per_grid):
        group = data[offset:offset+cells, :]   # shape (cells, 9)
        offset += cells
        for idx in range(cells):
            row = group[idx]
            # row: [x1, y1, x2, y2, class_logit0, ..., class_logit4]
            x1, y1, x2, y2 = row[0:4]
            # Apply sigmoid to class scores
            class_scores = 1.0 / (1.0 + np.exp(-row[4:]))
            max_score = np.max(class_scores)
            class_id = np.argmax(class_scores)
            if max_score >= conf_thresh:
                detections_list.append([x1, y1, x2, y2, max_score, class_id])

    if not detections_list:
        return np.empty((0, 6))

    boxes = np.array(detections_list)[:, :4]
    scores = np.array(detections_list)[:, 4]
    cls_ids = np.array(detections_list)[:, 5].astype(int)

    # 4. Remove padding and scale to original image dimensions
    boxes[:, 0] = boxes[:, 0] - left
    boxes[:, 1] = boxes[:, 1] - top
    boxes[:, 2] = boxes[:, 2] - left
    boxes[:, 3] = boxes[:, 3] - top
    boxes[:, 0] = boxes[:, 0] / r
    boxes[:, 1] = boxes[:, 1] / r
    boxes[:, 2] = boxes[:, 2] / r
    boxes[:, 3] = boxes[:, 3] / r
    # Clip to image bounds
    boxes[:, 0] = np.clip(boxes[:, 0], 0, w0)
    boxes[:, 1] = np.clip(boxes[:, 1], 0, h0)
    boxes[:, 2] = np.clip(boxes[:, 2], 0, w0)
    boxes[:, 3] = np.clip(boxes[:, 3], 0, h0)
    # Remove invalid boxes
    valid = (boxes[:, 2] > boxes[:, 0]) & (boxes[:, 3] > boxes[:, 1])
    boxes = boxes[valid]
    scores = scores[valid]
    cls_ids = cls_ids[valid]

    if len(boxes) == 0:
        return np.empty((0, 6))

    # 5. Non‑Maximum Suppression
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), conf_thresh, iou_thresh)
    if len(indices) == 0:
        return np.empty((0, 6))

    final = []
    for i in indices.flatten():
        final.append([boxes[i, 0], boxes[i, 1], boxes[i, 2], boxes[i, 3], scores[i], cls_ids[i]])
    return np.array(final)


def detect_kernel_contours(frame_bgr):
    """
    Detect kernel contours using OpenCV.
    Returns list of dicts with key 'box' [x1,y1,x2,y2] and optionally 'area'.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    contour_boxes = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 300:          # adjust based on your image resolution
            continue
        x, y, w, h = cv2.boundingRect(c)
        contour_boxes.append({"box": [x, y, x+w, y+h], "area": area})
    return contour_boxes
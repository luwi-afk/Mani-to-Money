# utils/vision_utils.py

import cv2
import numpy as np


def run_yolo(net, frame_bgr, imgsz=1280):
    """
    Run NCNN YOLO inference.
    Returns numpy detections.
    """

    img = cv2.resize(frame_bgr, (imgsz, imgsz))

    mat = net.Mat.from_pixels(
        img,
        net.Mat.PixelType.PIXEL_BGR,
        imgsz,
        imgsz
    )

    ex = net.create_extractor()
    ex.input("images", mat)

    ret, out = ex.extract("output")

    if ret != 0:
        return None

    detections = np.array(out)

    return detections


def detect_kernel_contours(frame_bgr):
    """
    Detect kernel contours using OpenCV.
    Returns list of bounding boxes.
    """

    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

    blur = cv2.GaussianBlur(gray, (5,5), 0)

    _, thresh = cv2.threshold(
        blur,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    contour_boxes = []

    for c in contours:

        area = cv2.contourArea(c)

        if area < 300:
            continue

        x, y, w, h = cv2.boundingRect(c)

        contour_boxes.append({
            "box": [x, y, x+w, y+h],
            "area": area
        })

    return contour_boxes
import cv2
import numpy as np
from picamera2 import Picamera2
import ncnn
import time

# -----------------------------
# Configuration
# -----------------------------
MODEL_PATH = "model/best_ncnn_model"
IMG_SIZE = 640
CONF_THRESHOLD = 0.25

PARAM_PATH = f"{MODEL_PATH}/model.ncnn.param"
BIN_PATH = f"{MODEL_PATH}/model.ncnn.bin"

# -----------------------------
# Load NCNN model
# -----------------------------
net = ncnn.Net()
net.load_param(PARAM_PATH)
net.load_model(BIN_PATH)

# -----------------------------
# Start Picamera2
# -----------------------------
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 640), "format": "RGB888"}
)
picam2.configure(config)
picam2.start()

time.sleep(2)

# -----------------------------
# Preprocess
# -----------------------------
def preprocess(frame):

    img = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))

    mat = ncnn.Mat.from_pixels(
        img,
        ncnn.Mat.PixelType.PIXEL_RGB,
        IMG_SIZE,
        IMG_SIZE
    )

    mean_vals = []
    norm_vals = [1/255.0, 1/255.0, 1/255.0]

    mat.substract_mean_normalize(mean_vals, norm_vals)

    return mat


# -----------------------------
# Draw detections
# -----------------------------
def draw_detections(frame, detections):

    for det in detections:

        x1, y1, x2, y2, conf, cls = det

        if conf < CONF_THRESHOLD:
            continue

        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)

        label = f"{int(cls)} {conf:.2f}"

        cv2.rectangle(frame, (x1,y1), (x2,y2), (0,255,0), 2)
        cv2.putText(
            frame,
            label,
            (x1, y1-10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0,255,0),
            2
        )

    return frame


# -----------------------------
# Postprocess (basic)
# -----------------------------
def postprocess(out):

    detections = []

    for i in range(out.h):

        values = out.row(i)

        x1 = values[0] * IMG_SIZE
        y1 = values[1] * IMG_SIZE
        x2 = values[2] * IMG_SIZE
        y2 = values[3] * IMG_SIZE
        conf = values[4]
        cls = values[5]

        detections.append([x1,y1,x2,y2,conf,cls])

    return detections


# -----------------------------
# Main Loop
# -----------------------------
while True:

    frame = picam2.capture_array()

    mat = preprocess(frame)

    ex = net.create_extractor()
    ex.input("in0", mat)

    ret, out = ex.extract("out0")

    detections = postprocess(out)

    annotated = draw_detections(frame, detections)

    cv2.imshow("NCNN Live Detection", annotated)

    if cv2.waitKey(1) & 0xFF == 27:
        break

picam2.stop()
cv2.destroyAllWindows()
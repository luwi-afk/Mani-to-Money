import os
import numpy as np
import ncnn
from utils.vision_utils import run_yolo
from utils.file_utils import project_path

class DetectionResult:
    """Mimics Ultralytics result for compatibility with extraction helpers."""
    def __init__(self, detections, class_names):
        self.detections = detections
        self.names = {i: name for i, name in enumerate(class_names)}
        self.boxes = self.Boxes(detections)

    class Boxes:
        def __init__(self, detections):
            if len(detections) == 0:
                self.xyxy = []
                self.conf = []
                self.cls = []
            else:
                self.xyxy = detections[:, :4]
                self.conf = detections[:, 4]
                self.cls = detections[:, 5].astype(int)

    def __bool__(self):
        return len(self.detections) > 0


class PeanutDetector:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = project_path("models/best_ncnn_model")

        param_path = os.path.join(model_path, "model.ncnn.param")
        bin_path = os.path.join(model_path, "model.ncnn.bin")

        if not os.path.exists(param_path) or not os.path.exists(bin_path):
            raise FileNotFoundError(f"NCNN model files not found in {model_path}")

        self.net = ncnn.Net()
        self.net.load_param(param_path)
        self.net.load_model(bin_path)

        self.imgsz = 640
        self.class_names = ["broken", "damage", "normal", "shriveled"]
        self.num_classes = len(self.class_names)

    def predict(self, frame_bgr, conf=0.5, imgsz=640):
        detections = run_yolo(self.net, frame_bgr, imgsz, conf_thresh=conf)
        if detections is None or len(detections) == 0:
            return DetectionResult(np.empty((0,6)), self.class_names)
        return DetectionResult(detections, self.class_names)
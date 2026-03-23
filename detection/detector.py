# detector.py
from ultralytics import YOLO
import numpy as np

class DetectionResult:
    """Mimics Ultralytics result for compatibility with extraction helpers."""
    def __init__(self, detections, class_names):
        self.detections = detections
        self.names = {i: name for i, name in enumerate(class_names)}
        self.boxes = self.Boxes(detections)

    class Boxes:
        def __init__(self, detections):
            if len(detections) == 0:
                self.xyxy = np.empty((0,4))
                self.conf = np.empty((0,))
                self.cls = np.empty((0,), dtype=int)
            else:
                self.xyxy = detections[:, :4]
                self.conf = detections[:, 4]
                self.cls = detections[:, 5].astype(int)

    def __bool__(self):
        return len(self.detections) > 0

class PeanutDetector:
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)  # loads best.pt
        self.class_names = ["broken", "damage", "normal", "shriveled"]
        self.num_classes = len(self.class_names)


    def predict(self, frame_bgr, conf=0.5, imgsz=640):
        results = self.model(frame_bgr, conf=conf, imgsz=imgsz, verbose=False)
        if not results or len(results[0].boxes) == 0:
            return DetectionResult(np.empty((0, 6)), self.class_names)

        # Convert Ultralytics Results -> N x 6 array
        dets = results[0].boxes.xyxy.cpu().numpy()  # shape N x 4
        confs = results[0].boxes.conf.cpu().numpy().reshape(-1, 1)  # shape N x 1
        cls = results[0].boxes.cls.cpu().numpy().reshape(-1, 1).astype(int)  # shape N x 1
        detections = np.hstack([dets, confs, cls])  # N x 6
        return DetectionResult(detections, self.class_names)
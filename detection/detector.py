import os
import cv2
import numpy as np
import ncnn
from utils.file_utils import project_path

class PeanutDetector:
    def __init__(self, model_path=None):
        if model_path is None:
            model_path = project_path("models/peanut_model_ncnn_model")

        param_path = os.path.join(model_path, "model.ncnn.param")
        bin_path = os.path.join(model_path, "model.ncnn.bin")

        if not os.path.exists(param_path) or not os.path.exists(bin_path):
            raise FileNotFoundError(f"NCNN model files not found in {model_path}")

        self.net = ncnn.Net()
        self.net.load_param(param_path)
        self.net.load_model(bin_path)

        self.imgsz = 640
        self.class_names = ["broken", "moldy", "peanut_kernel", "pest_damage", "shriveled"]
        self.num_classes = len(self.class_names)
        self.names_dict = {i: name for i, name in enumerate(self.class_names)}

        self.input_name = "in0"
        self.output_name = "out0"

    def preprocess(self, frame_bgr):
        img = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.imgsz, self.imgsz))
        mat_in = ncnn.Mat.from_pixels(
            img.tobytes(),
            ncnn.Mat.PixelType.PIXEL_RGB,
            self.imgsz,
            self.imgsz
        )
        mat_in.substract_mean_normalize([], [1/255.0, 1/255.0, 1/255.0])
        return mat_in

    def postprocess(self, mat_out, orig_shape, conf_thres=0.25, iou_thres=0.45):
        out_np = np.array(mat_out)   # shape: (9, 8400)
        if out_np.ndim != 2 or out_np.shape[0] != 9 or out_np.shape[1] != 8400:
            raise ValueError(f"Unexpected output shape: {out_np.shape}")

        out_np = out_np.T  # (8400, 9)

        boxes = out_np[:, :4]
        scores = out_np[:, 4:]

        max_scores = np.max(scores, axis=1, keepdims=True)
        class_ids = np.argmax(scores, axis=1).reshape(-1, 1)

        keep = max_scores.flatten() >= conf_thres
        if not np.any(keep):
            return None

        boxes = boxes[keep]
        max_scores = max_scores[keep]
        class_ids = class_ids[keep]

        boxes = np.hstack([
            boxes[:, 0:1] - boxes[:, 2:3] / 2,
            boxes[:, 1:2] - boxes[:, 3:4] / 2,
            boxes[:, 0:1] + boxes[:, 2:3] / 2,
            boxes[:, 1:2] + boxes[:, 3:4] / 2
        ])

        detections = np.hstack([boxes, max_scores, class_ids])
        detections = self.nms(detections, iou_thres)

        if len(detections) == 0:
            return None

        scale_x = orig_shape[1] / self.imgsz
        scale_y = orig_shape[0] / self.imgsz
        detections[:, [0, 2]] *= scale_x
        detections[:, [1, 3]] *= scale_y

        class Boxes:
            def __init__(self, dets):
                self.xyxy = dets[:, :4]
                self.conf = dets[:, 4:5]
                self.cls = dets[:, 5:6].astype(int)
                self.data = dets
            def __len__(self):
                return len(self.xyxy)

        class Result:
            def __init__(self, boxes, names):
                self.boxes = boxes
                self.names = names

        return Result(Boxes(detections), self.names_dict)

    def nms(self, detections, iou_thres):
        if len(detections) == 0:
            return detections

        boxes = detections[:, :4]
        scores = detections[:, 4]

        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(iou <= iou_thres)[0]
            order = order[inds + 1]

        return detections[keep]

    def predict(self, frame_bgr, conf=0.25, iou=0.45, imgsz=640):
        mat_in = self.preprocess(frame_bgr)
        with self.net.create_extractor() as ex:
            ex.input(self.input_name, mat_in)
            ret, mat_out = ex.extract(self.output_name)
            if ret != 0:
                raise RuntimeError(f"Extract failed with code {ret}")
        return self.postprocess(mat_out, frame_bgr.shape[:2], conf, iou)
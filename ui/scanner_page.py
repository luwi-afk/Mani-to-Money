import os
from datetime import datetime

import cv2
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QSizePolicy
)

from camera.camera_manager import init_camera, get_camera, release_camera
from detection.detector import PeanutDetector
from utils.file_utils import project_path, ensure_dir
from utils.pdf_report import generate_scan_report
from utils.app_settings import get_max_price_per_kg


# ---------------- Shared annotation helpers (with clipping & limiting) ----------------
def _draw_kernel_grade_price(frame_bgr, kernel_results):
    """
    Draw 1 green box per kernel labeled with Grade + ₱/kg.
    Limit to top 50 by score to avoid overload.
    """
    if not kernel_results:
        return frame_bgr

    h, w = frame_bgr.shape[:2]

    # Sort by score descending and take top 50
    sorted_kernels = sorted(kernel_results, key=lambda k: k.get("score", 0), reverse=True)[:50]

    for k in sorted_kernels:
        x1, y1, x2, y2 = map(int, k["box"])
        # Clip to image bounds
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))
        if x2 <= x1 or y2 <= y1:
            continue  # skip invalid box

        grade = k.get("grade", "Unknown")
        ppk = float(k.get("price_per_kg", 0.0))

        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)

        text = f"{grade}  Php{ppk:.2f}/kg"
        ty = max(20, y1 - 8)
        cv2.putText(
            frame_bgr, text, (x1, ty),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2
        )
    return frame_bgr


def _draw_defects(frame_bgr, defects):
    """
    Draw red defect boxes + defect label.
    Limit to top 50 by confidence.
    """
    if not defects:
        return frame_bgr

    h, w = frame_bgr.shape[:2]

    # Sort by confidence descending and take top 50
    sorted_defects = sorted(defects, key=lambda d: d.get("conf", 0), reverse=True)[:50]

    for d in sorted_defects:
        x1, y1, x2, y2 = map(int, d["box"])
        # Clip to image bounds
        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))
        if x2 <= x1 or y2 <= y1:
            continue

        label = str(d.get("label", "")).strip()

        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(
            frame_bgr, label, (x1, max(20, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2
        )
    return frame_bgr


class OfflineScanWorker(QThread):
    # tray_avg, tray_grade, price_per_kg, pdf_path, kernel_results
    finished = pyqtSignal(float, str, float, str, object)
    failed = pyqtSignal(str)

    def __init__(self, detector, frame_bgr, yolo_result=None,
                 conf=0.25, iou=0.45, max_price_per_kg=250.0):
        super().__init__()
        self.detector = detector
        self.frame_bgr = frame_bgr
        self.yolo_result = yolo_result
        self.conf = conf
        self.iou = iou
        self.max_price_per_kg = float(max_price_per_kg)

    def run(self):
        try:
            from logics.grading_pricing_func import (
                get_defect_boxes, compute_kernel_results, get_kernel_boxes
            )
            LABEL_MAP = {
                "pest damage": "pest_damage",
                "pest-damage": "pest_damage",
            }

            if self.yolo_result is not None:
                result = self.yolo_result
            else:
                result = self.detector.predict(self.frame_bgr, conf=self.conf, iou=self.iou, imgsz=640)

            if result is None:
                self.failed.emit("Detection returned None")
                return

            kernel_boxes = get_kernel_boxes(result, conf_min=0.10, kernel_label="peanut_kernel")
            if not kernel_boxes:
                self.finished.emit(0.0, "No Detection", 0.0, "", [])
                return

            defects = get_defect_boxes(
                result,
                conf_min=0.10,
                label_map=LABEL_MAP,
                kernel_label="peanut_kernel"
            )

            kernel_results, tray_avg, tray_grade, price_per_kg = compute_kernel_results(
                kernel_boxes,
                defects,
                max_price_per_kg=self.max_price_per_kg,
                max_distance_px=100
            )

            annotated = self.frame_bgr.copy()
            annotated = _draw_kernel_grade_price(annotated, kernel_results)
            annotated = _draw_defects(annotated, defects)

            out_dir = project_path("receipts")
            ensure_dir(out_dir)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_path = os.path.join(out_dir, f"scan_{ts}.pdf")

            generate_scan_report(
                pdf_path=pdf_path,
                annotated_bgr_image=annotated,
                tray_avg_score=tray_avg,
                tray_grade=tray_grade,
                price_per_kg=price_per_kg,
                kernel_results=kernel_results
            )

            self.finished.emit(tray_avg, tray_grade, price_per_kg, pdf_path, kernel_results)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(e) + "\n" + traceback.format_exc())


class ScannerPage(QWidget):
    def __init__(self):
        super().__init__()

        self.camera = None
        self.detector = PeanutDetector()
        self.conf = 0.25
        self.iou = 0.45
        self.last_frame_bgr = None
        self.last_result = None
        self._frame_i = 0
        self.infer_every = 6

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 15, 5, 15)
        layout.setSpacing(10)

        self.instruction = QLabel("Position Tray then Click Scan")
        self.instruction.setAlignment(Qt.AlignCenter)
        self.instruction.setFixedHeight(38)
        self.instruction.setStyleSheet("""
            QLabel {
                color: #2e2e2e;
                font-size: 18px;
                font-weight: bold;
                background: #F2E8C9;
                border-radius: 10px;
                padding: 6px 12px;
            }
        """)
        layout.addWidget(self.instruction)

        self.video = QLabel()
        self.video.setMinimumSize(750, 450) #feedback video size
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setStyleSheet("background: transparent;")
        layout.addWidget(self.video, stretch=1)

        btn_container = QWidget()
        btn_container.setFixedSize(160, 70)
        btns = QHBoxLayout(btn_container)
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setAlignment(Qt.AlignCenter)

        self.scan = QPushButton("Scan")
        self.scan.setFixedSize(140, 55)
        self.scan.setCursor(Qt.PointingHandCursor)
        self.scan.setStyleSheet("""
            QPushButton {
                background:#4CAF50;
                color:white;
                font-size:18px;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover { background:#388E3C; }
            QPushButton:disabled { background:#9E9E9E; }
        """)
        self.scan.clicked.connect(self.on_scan_clicked)

        btns.addWidget(self.scan)
        layout.addWidget(btn_container, alignment=Qt.AlignCenter)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    # ---- Page lifecycle ----
    def start_camera(self):
        init_camera()
        self.camera = get_camera()
        if not self.camera:
            QMessageBox.critical(self, "Camera Error", "Camera not available.")
            return False

        self.last_frame_bgr = None
        self.last_result = None
        self._frame_i = 0

        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)

        if not self.timer.isActive():
            self.timer.start(30)

        return True

    def stop_camera(self):
        if self.timer.isActive():
            self.timer.stop()

        self.video.clear()
        self.last_frame_bgr = None
        self.last_result = None

        release_camera()
        self.camera = None

        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)

    def set_instruction(self, text: str, scanning: bool = False):
        if scanning:
            self.instruction.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 18px;
                    font-weight: bold;
                    background: #FF9800;
                    border-radius: 10px;
                    padding: 6px 12px;
                }
            """)
        else:
            self.instruction.setStyleSheet("""
                QLabel {
                    color: #2e2e2e;
                    font-size: 18px;
                    font-weight: bold;
                    background: #F2E8C9;
                    border-radius: 10px;
                    padding: 6px 12px;
                }
            """)
        self.instruction.setText(text)

    # ---- Preview drawing methods ----
    def draw_kernel_grade_price(self, frame_bgr, result):
        from logics.grading_pricing_func import (
            get_kernel_boxes, get_defect_boxes, compute_kernel_results
        )

        if result is None or result.boxes is None or len(result.boxes.xyxy) == 0:
            return frame_bgr

        LABEL_MAP = {
            "pest damage": "pest_damage",
            "pest-damage": "pest_damage",
        }

        kernel_boxes = get_kernel_boxes(result, conf_min=0.10, kernel_label="peanut_kernel")
        defects = get_defect_boxes(result, conf_min=0.10, label_map=LABEL_MAP, kernel_label="peanut_kernel")

        max_price = get_max_price_per_kg()
        kernel_results, _, _, _ = compute_kernel_results(
            kernel_boxes, defects, max_price_per_kg=max_price
        )

        return _draw_kernel_grade_price(frame_bgr, kernel_results)

    def draw_defects_feedback(self, frame_bgr, result):
        from logics.grading_pricing_func import get_defect_boxes

        if result is None or result.boxes is None or len(result.boxes.xyxy) == 0:
            return frame_bgr

        LABEL_MAP = {
            "pest damage": "pest_damage",
            "pest-damage": "pest_damage",
        }

        defects = get_defect_boxes(
            result,
            conf_min=0.10,
            label_map=LABEL_MAP,
            kernel_label="peanut_kernel"
        )

        return _draw_defects(frame_bgr, defects)

    # ---- Realtime loop ----
    def update_frame(self):
        if not self.camera:
            return

        ok, frame = self.camera.read()
        if not ok or frame is None:
            return

        frame = cv2.flip(frame, 1)
        self.last_frame_bgr = frame.copy()
        self._frame_i += 1

        if (self._frame_i % self.infer_every) == 0:
            try:
                self.last_result = self.detector.predict(frame, conf=self.conf, iou=self.iou, imgsz=640)
            except Exception:
                self.last_result = None

        annotated = frame.copy()

        if self.last_result is not None and self.last_result.boxes is not None and len(self.last_result.boxes.xyxy) > 0:
            try:
                annotated = self.draw_kernel_grade_price(annotated, self.last_result)
            except Exception:
                pass
            try:
                annotated = self.draw_defects_feedback(annotated, self.last_result)
            except Exception:
                pass

        self._show_frame(annotated)

    def _show_frame(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(qimg).scaled(
            self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video.setPixmap(pix)

    # ---- Scan button ----
    def on_scan_clicked(self):
        if self.last_frame_bgr is None:
            QMessageBox.warning(self, "Scan", "No camera frame yet. Hold still for a second.")
            return
        if self.last_result is None:
            QMessageBox.warning(self, "Scan", "No detections yet. Wait 1–2 seconds then try again.")
            return

        self.scan.setEnabled(False)
        self.scan.setText("Scanning...")
        self.set_instruction("Scanning… Please hold still", scanning=True)

        frame = self.last_frame_bgr.copy()
        result = self.last_result
        max_price = get_max_price_per_kg()

        self.worker = OfflineScanWorker(
            detector=self.detector,
            frame_bgr=frame,
            yolo_result=result,
            conf=self.conf,
            iou=self.iou,
            max_price_per_kg=max_price
        )
        self.worker.finished.connect(self.on_scan_done)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.start()

    def on_scan_done(self, tray_avg, tray_grade, price_per_kg, pdf_path, kernel_results):
        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)

        if not pdf_path and not kernel_results:
            QMessageBox.warning(
                self,
                "Scan Failed",
                "No peanut kernels detected.\n\n"
                "Try again with:\n"
                "• Better lighting\n"
                "• Proper tray positioning\n"
                "• Clear view of kernels"
            )
            return

        defect_counts = {}
        class_counts = {}
        for k in (kernel_results or []):
            g = k.get("grade", "Unknown")
            class_counts[g] = class_counts.get(g, 0) + 1
            for d in k.get("defects", []):
                defect_counts[d] = defect_counts.get(d, 0) + 1

        detected = len(kernel_results or [])

        defect_order = ["moldy", "pest_damage", "shriveled", "broken"]
        defect_lines = [f"{d}: {defect_counts.get(d, 0)}" for d in defect_order]

        grade_order = ["Extra Class", "Class I", "Class II", "Reject / Non-trade"]
        grade_lines = [f"{g}: {class_counts.get(g, 0)}" for g in grade_order]

        if detected == 0:
            QMessageBox.warning(
                self,
                "Scan Complete",
                "No peanut kernels detected.\nTry again with better lighting or positioning."
            )
            return

        try:
            from utils.ticket import print_ticket
            print_ticket(
                defect_lines=defect_lines,
                grade_lines=grade_lines,
                detected=detected,
                tray_avg=tray_avg,
                tray_grade=tray_grade,
                price_per_kg=price_per_kg,
                pdf_path=pdf_path
            )
        except Exception:
            pass  #Printer not available – ignore silently

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        msg = (
            "SCAN SUMMARY\n"
            f"Date: {date_str}\n"
            f"Time: {time_str}\n\n"
            "DEFECT COUNTS\n"
            + "\n".join(defect_lines)
            + "\n\nKERNELS PER CLASS\n"
            + f"Detected kernels: {detected}\n"
            + "\n".join(grade_lines)
            + f"\n\nTray Avg Score: {tray_avg:.2f}\n"
            + f"Tray Avg Grade: {tray_grade}\n"
            + f"Estimated Price per Kg: Php{price_per_kg:.2f} per kg\n\n"
            + f"Scan saved:\n{pdf_path}"
        )

        QMessageBox.information(self, "Scan Complete", msg)

    def on_scan_failed(self, msg: str):
        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)
        QMessageBox.critical(self, "Offline Detection Error", msg)
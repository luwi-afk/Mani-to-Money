# ui/scanner_page.py
import os
import numpy as np
from datetime import datetime

import cv2
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QSizePolicy
)

from camera.camera_manager import (
    init_camera, read_camera, get_camera, release_camera,
    is_using_picamera
)
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

    printer_status_changed = pyqtSignal(str, bool)  # status text, connected flag

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
        self._failed_reads = 0
        self._using_module3 = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
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
        self.video.setMinimumSize(765, 420) #cam feed size
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setStyleSheet("background: transparent;")
        layout.addWidget(self.video, stretch=1)

        # Button container
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

    def start_camera(self):
        """Initialize and start camera"""
        try:
            # Read resolution and FPS from settings
            from utils.app_settings import get_camera_resolution, get_camera_fps
            width, height = get_camera_resolution()
            fps = get_camera_fps()

            if not init_camera(width=width, height=height, fps=fps):
                QMessageBox.critical(self, "Camera Error", "Camera not available.")
                return False

            self.camera = get_camera()
            if not self.camera:
                QMessageBox.critical(self, "Camera Error", "Camera not available.")
                return False

            self._using_module3 = is_using_picamera()
            self.last_frame_bgr = None
            self.last_result = None
            self._frame_i = 0
            self._failed_reads = 0

            self.scan.setEnabled(True)
            self.scan.setText("Scan")
            self.set_instruction("Position Tray then Click Scan", scanning=False)

            if not self.timer.isActive():
                self.timer.start(30)

            return True

        except Exception as e:
            print(f"Camera error: {e}")
            return False

    def stop_camera(self):
        """Stop camera and cleanup"""
        if self.timer.isActive():
            self.timer.stop()

        self.video.clear()
        self.last_frame_bgr = None
        self.last_result = None

        release_camera()
        self.camera = None
        self._using_module3 = False

        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)

    def set_instruction(self, text: str, scanning: bool = False):
        """Update instruction label style"""
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

    def _show_no_signal(self):
        """Show 'No Signal' placeholder when camera fails"""
        blank = np.zeros((420, 747, 3), dtype=np.uint8)
        cv2.putText(blank, "No Camera Signal", (200, 210),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(blank, "Check Camera Connection", (150, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        self._show_frame(blank)

    # ---- Preview drawing methods ----
    def draw_kernel_grade_price(self, frame_bgr, result):
        """Draw kernel annotations on frame"""
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
        """Draw defect annotations on frame"""
        from logics.grading_pricing_func import get_defect_boxes

        if result is None or result.boxes is None or len(result.boxes.xyxy) == 0:
            return frame_bgr

        LABEL_MAP = {
            "pest damage": "pest_damage",
            "pest-damage": "pest_damage",
        }

        defects = get_defect_boxes(
            result,
            conf_min=0.25,
            label_map=LABEL_MAP,
            kernel_label="peanut_kernel"
        )

        return _draw_defects(frame_bgr, defects)

    # ---- Realtime loop ----
    def update_frame(self):
        """Main update loop for camera feed"""
        if not self.camera:
            return

        try:
            ok, frame = read_camera()
            if not ok or frame is None:
                self._failed_reads += 1
                if self._failed_reads > 10:
                    self._show_no_signal()
                return

            self._failed_reads = 0

            # Flip horizontally for mirror effect
            frame = cv2.flip(frame, 1)
            self.last_frame_bgr = frame.copy()
            self._frame_i += 1

            # Run inference every N frames
            if (self._frame_i % self.infer_every) == 0:
                try:
                    self.last_result = self.detector.predict(
                        frame, conf=self.conf, iou=self.iou, imgsz=640
                    )
                except Exception:
                    self.last_result = None

            # Draw annotations
            annotated = frame.copy()
            if self.last_result is not None:
                try:
                    if hasattr(self.last_result, 'boxes') and len(self.last_result.boxes.xyxy) > 0:
                        annotated = self.draw_kernel_grade_price(annotated, self.last_result)
                        annotated = self.draw_defects_feedback(annotated, self.last_result)
                except Exception:
                    pass

            self._show_frame(annotated)

        except Exception:
            pass

    def _show_frame(self, frame_bgr):
        try:
            rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            pix = QPixmap.fromImage(qimg)

            label_size = self.video.size()
            scaled_pix = pix.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            final_pix = QPixmap(label_size)
            final_pix.fill(Qt.transparent)
            painter = QPainter(final_pix)
            x = (label_size.width() - scaled_pix.width()) // 2
            y = (label_size.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)
            painter.end()

            self.video.setPixmap(final_pix)
        except Exception as e:
            print(f"Display error: {e}")

    # ---- Scan button ----
    def on_scan_clicked(self):
        """Handle scan button click"""
        if self.last_frame_bgr is None:
            QMessageBox.warning(self, "Scan", "No camera frame yet. Please wait for camera feed.")
            return
        if self.last_result is None:
            QMessageBox.warning(self, "Scan", "No detections yet. Please wait 1-2 seconds.")
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
        """Handle successful scan with properly sized message box"""
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

        # Count defects and grades
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

        # Get max price for display
        max_price = get_max_price_per_kg()

        # Try to print ticket - with error handling and status updates
        try:
            from utils.ticket import print_ticket
            success = print_ticket(
                defect_lines=defect_lines,
                grade_lines=grade_lines,
                detected=detected,
                tray_avg=tray_avg,
                tray_grade=tray_grade,
                price_per_kg=price_per_kg,
                max_price_per_kg=max_price,
                pdf_path=pdf_path
            )

            # Update printer status based on result
            if success:
                self.printer_status_changed.emit("Ready", True)
            else:
                self.printer_status_changed.emit("Not Connected", False)

        except Exception as e:
            print(f"Ticket printing error: {e}")
            self.printer_status_changed.emit("Error", False)

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")

        # Create a condensed message for the message box
        # Only show summary, not all details
        summary_msg = (
            f"✅ SCAN COMPLETE\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Date: {date_str}\n"
            f"Time: {time_str}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"Kernels detected: {detected}\n"
            f"Tray Grade: {tray_grade}\n"
            f"Price: Php{price_per_kg:.2f}/kg\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"PDF saved"
        )

        # Create message box with proper size
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Scan Complete")
        msg_box.setText(summary_msg)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)

        # Add a "Details" button if user wants to see full breakdown
        details_btn = msg_box.addButton("View Details", QMessageBox.ActionRole)

        # Set fixed size to fit your window (max 400 height)
        msg_box.setFixedSize(400, 300)  # Width, Height - adjust as needed

        # Show the message box
        result = msg_box.exec_()

        # If user clicked Details, show full report in a separate dialog
        if msg_box.clickedButton() == details_btn:
            self.show_full_report(date_str, time_str, max_price, defect_lines,
                                  grade_lines, detected, tray_avg, tray_grade,
                                  price_per_kg, pdf_path)

    def show_full_report(self, date_str, time_str, max_price, defect_lines,
                         grade_lines, detected, tray_avg, tray_grade,
                         price_per_kg, pdf_path):
        """Show full scrollable report in a separate dialog"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("Detailed Scan Report")
        dialog.resize(500, 450)  # Fixed size for details dialog

        layout = QVBoxLayout(dialog)

        # Scrollable text area
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)

        # Format with HTML for better readability
        html = f"""
        <h2>📊 DETAILED SCAN REPORT</h2>
        <hr>
        <table width='100%'>
            <tr><td><b>Date:</b></td><td>{date_str}</td></tr>
            <tr><td><b>Time:</b></td><td>{time_str}</td></tr>
            <tr><td><b>Max Price:</b></td><td>Php{max_price:.2f}/kg</td></tr>
        </table>

        <h3>📉 DEFECT COUNTS</h3>
        <table width='100%' border='1' cellpadding='4'>
            <tr><th>Defect Type</th><th>Count</th></tr>
            {"".join(f"<tr><td>{d.split(':')[0]}</td><td>{d.split(':')[1]}</td></tr>" for d in defect_lines)}
        </table>

        <h3>🥜 KERNEL GRADES</h3>
        <table width='100%' border='1' cellpadding='4'>
            <tr><th>Grade</th><th>Count</th></tr>
            <tr><td><b>Total Detected</b></td><td><b>{detected}</b></td></tr>
            {"".join(f"<tr><td>{g.split(':')[0]}</td><td>{g.split(':')[1]}</td></tr>" for g in grade_lines)}
        </table>

        <h3>📈 FINAL RESULTS</h3>
        <table width='100%'>
            <tr><td><b>Tray Avg Score:</b></td><td>{tray_avg:.2f}</td></tr>
            <tr><td><b>Tray Avg Grade:</b></td><td>{tray_grade}</td></tr>
            <tr><td><b>Estimated Price:</b></td><td>Php{price_per_kg:.2f}/kg</td></tr>
        </table>

        <p><small><b>PDF saved at:</b><br>{pdf_path}</small></p>
        """

        text_edit.setHtml(html)
        layout.addWidget(text_edit)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setFixedSize(100, 30)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        dialog.exec_()

    def on_scan_failed(self, msg: str):
        """Handle scan failure"""
        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)
        QMessageBox.critical(self, "Offline Detection Error", msg)
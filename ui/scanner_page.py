import os
import numpy as np
from datetime import datetime

import cv2
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QMessageBox, QSizePolicy, QCheckBox
)

from camera.camera_manager import (
    init_camera, read_camera, get_camera, release_camera,
    is_using_picamera
)
from detection.detector import PeanutDetector
from utils.file_utils import project_path, ensure_dir
from utils.pdf_report import generate_scan_report
from utils.app_settings import get_max_price_per_kg
from utils.vision_utils import detect_kernel_contours

# ---------------- Shared annotation helpers ----------------
def _draw_kernel_grade_price(frame_bgr, kernel_results, max_price_per_kg=250.0):
    """Draw kernel boxes and labels."""
    if not kernel_results:
        return frame_bgr

    h, w = frame_bgr.shape[:2]

    sorted_kernels = sorted(kernel_results, key=lambda k: k.get("score", 0), reverse=True)[:50]

    for k in sorted_kernels:
        x1, y1, x2, y2 = map(int, k["box"])
        x1 = max(0, min(w-1, x1)); y1 = max(0, min(h-1, y1))
        x2 = max(0, min(w-1, x2)); y2 = max(0, min(h-1, y2))

        if x2 <= x1 or y2 <= y1:
            continue

        defects = k.get("defects", [])
        grade = k.get("grade", "Unknown")
        price = float(k.get("price_per_kg", 0.0))
        has_normal = k.get("has_normal", False)

        if not defects and has_normal:
            price = k.get("max_price", max_price_per_kg)

        # Draw green kernel box
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        text = f"{grade}  P{price:.2f}/kg"
        cv2.putText(frame_bgr, text, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 0), 2)

        # Draw red defect boxes (skip "normal")
        for d in defects:
            label = str(d.get("label", "")).strip().lower()
            if label == "normal":
                continue
            dx1, dy1, dx2, dy2 = map(int, d.get("box", [0, 0, 0, 0]))
            dx1 = max(0, min(w-1, dx1)); dy1 = max(0, min(h-1, dy1))
            dx2 = max(0, min(w-1, dx2)); dy2 = max(0, min(h-1, dy2))
            if dx2 <= dx1 or dy2 <= dy1:
                continue
            cv2.rectangle(frame_bgr, (dx1, dy1), (dx2, dy2), (0, 0, 255), 2)
            cv2.putText(frame_bgr, label, (dx1, max(20, dy1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    return frame_bgr

# ---------------- Helper function for detection & grading ----------------
def get_kernel_results_from_frame(frame_bgr, detector, conf=0.50, max_price_per_kg=250.0):
    """
    Run detection on a frame, map boxes to kernel contours, and compute grades/prices.
    Returns (kernel_results, tray_avg_score, tray_grade, estimated_price_per_kg)
    """
    from logics.grading_pricing_func import (
        assign_boxes_to_contours_all_classes,
        compute_kernel_results_from_kernel_data
    )

    # Run detection
    result = detector.predict(frame_bgr, conf=conf, imgsz=640)
    if result is None:
        return [], 0.0, "No Detection", 0.0

    # Detect contours
    contours = detect_kernel_contours(frame_bgr)
    kernel_data = assign_boxes_to_contours_all_classes(contours, result)

    if not kernel_data:
        return [], 0.0, "No Detection", 0.0

    # Compute grades, prices
    kernel_results, tray_avg, tray_grade, price = compute_kernel_results_from_kernel_data(
        kernel_data, max_price_per_kg=max_price_per_kg
    )

    return kernel_results, tray_avg, tray_grade, price

# ---------------- Worker Thread ----------------
class OfflineScanWorker(QThread):
    # MODIFIED: Added an extra 'object' for the annotated image
    finished = pyqtSignal(float, str, float, str, object, object)   # tray_avg, tray_grade, price, pdf_path, kernel_results, image
    failed = pyqtSignal(str)

    def __init__(self, detector, frame_bgr, yolo_result=None,
                 conf=0.50, max_price_per_kg=250.0):
        super().__init__()
        self.detector = detector
        self.frame_bgr = frame_bgr
        self.yolo_result = yolo_result
        self.conf = conf
        self.max_price_per_kg = float(max_price_per_kg)

    def run(self):
        try:
            # Use the helper function
            kernel_results, tray_avg, tray_grade, price = get_kernel_results_from_frame(
                self.frame_bgr, self.detector, self.conf, self.max_price_per_kg
            )

            if not kernel_results:
                # MODIFIED: Emit with image=None
                self.finished.emit(0.0, "No Detection", 0.0, "", [], None)
                return

            # Draw annotated image
            annotated = _draw_kernel_grade_price(
                self.frame_bgr.copy(), kernel_results, self.max_price_per_kg
            )

            # Count defects for PDF
            defect_counts = {}
            for k in kernel_results or []:
                for d in k.get("defects", []):
                    label = str(d.get("label", "")).lower()
                    if label:
                        defect_counts[label] = defect_counts.get(label, 0) + 1
            defect_lines = [f"{label}:{count}" for label, count in defect_counts.items()]

            # Save PDF
            out_dir = project_path("receipts")
            ensure_dir(out_dir)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            pdf_path = os.path.join(out_dir, f"scan_{ts}.pdf")

            generate_scan_report(
                pdf_path=pdf_path,
                annotated_bgr_image=annotated,
                tray_avg_score=tray_avg,
                tray_grade=tray_grade,
                price_per_kg=price,
                kernel_results=kernel_results,
            )

            # MODIFIED: Emit the annotated image as well
            self.finished.emit(tray_avg, tray_grade, price, pdf_path, kernel_results, annotated)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed.emit(str(e) + "\n" + traceback.format_exc())

# ---------------- Scanner Page ----------------
class ScannerPage(QWidget):

    printer_status_changed = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()

        self.camera = None
        self.detector = PeanutDetector("models/best.pt")
        self.conf = 0.50
        self.last_frame_bgr = None
        self.last_result = None
        self._frame_i = 0
        self._failed_reads = 0
        self._using_module3 = False

        # Live detection members (frame-skipping)
        self.live_detection_enabled = False
        self.live_result = None                     # stores kernel_results for live display
        self.live_inference_every_n_frames = 5      # Run detection every 5 frames (adjust this)
        self.frame_counter = 0

        # UI setup
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Instruction label
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

        # Video preview
        self.video = QLabel()
        self.video.setMinimumSize(765, 420)
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setStyleSheet("background: transparent;")
        layout.addWidget(self.video, stretch=1)

        # Control panel (checkboxes and scan button)
        controls = QHBoxLayout()
        controls.setAlignment(Qt.AlignCenter)

        # Live detection checkbox
        self.live_checkbox = QCheckBox("Live Detection")
        self.live_checkbox.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.live_checkbox.toggled.connect(self.toggle_live_detection)
        controls.addWidget(self.live_checkbox)

        # Scan button container
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
        controls.addWidget(btn_container)

        layout.addLayout(controls)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

    # ---------------- Live detection toggling ----------------
    def toggle_live_detection(self, checked):
        self.live_detection_enabled = checked
        if not checked:
            self.live_result = None   # clear old results when turned off
        # (No timer start/stop needed; detection is triggered by frame counter)

    def run_live_detection(self):
        """Runs detection on the latest frame and stores results."""
        if not self.live_detection_enabled:
            return
        if self.last_frame_bgr is None:
            return

        # Copy the clean frame (detection may be heavy)
        frame_copy = self.last_frame_bgr.copy()
        try:
            # Use helper function to get kernel results
            kernel_results, _, _, _ = get_kernel_results_from_frame(
                frame_copy, self.detector, self.conf, get_max_price_per_kg()
            )
            self.live_result = kernel_results
        except Exception as e:
            print(f"Live detection error: {e}")

    # ---------------- Camera ----------------
    def start_camera(self):
        try:
            from utils.app_settings import get_camera_fps
            width, height = 640, 640
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

            # Reset frame counter for consistent start
            self.frame_counter = 0

            self.scan.setEnabled(True)
            self.scan.setText("Scan")
            self.set_instruction("Position Tray then Click Scan", scanning=False)

            if not self.timer.isActive():
                self.timer.start(30)   # ~33 fps, adjust as needed

            return True

        except Exception as e:
            print(f"Camera error: {e}")
            return False

    def stop_camera(self):
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
        blank = np.zeros((420, 747, 3), dtype=np.uint8)
        cv2.putText(blank, "No Camera Signal", (200, 210),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(blank, "Check Camera Connection", (150, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        self._show_frame(blank)

    # ---------------- Frame Handling ----------------
    def update_frame(self):
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
            frame = cv2.flip(frame, 1)
            self.last_frame_bgr = frame.copy()

            # Live detection with frame skipping
            if self.live_detection_enabled:
                self.frame_counter += 1
                if self.frame_counter >= self.live_inference_every_n_frames:
                    self.frame_counter = 0
                    self.run_live_detection()   # runs detection on the latest frame

            self._show_frame(frame)
        except Exception as e:
            print("Camera update error:", e)

    def _show_frame(self, frame_bgr):
        try:
            # If live detection is enabled and we have results, draw them on a copy
            if self.live_detection_enabled and self.live_result is not None:
                display_frame = frame_bgr.copy()
                display_frame = _draw_kernel_grade_price(
                    display_frame, self.live_result, get_max_price_per_kg()
                )
            else:
                display_frame = frame_bgr

            rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
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

    # ---------------- Scan ----------------
    def on_scan_clicked(self):
        if self.last_frame_bgr is None:
            QMessageBox.warning(self, "Scan", "No camera frame yet. Please wait for camera feed.")
            return

        # Save live detection state and temporarily disable it
        self._live_was_enabled = self.live_detection_enabled
        if self._live_was_enabled:
            self.live_detection_enabled = False  # stop new live detections
            # Also stop the frame counter from triggering
            self.frame_counter = 0

        self.scan.setEnabled(False)
        self.scan.setText("Scanning...")
        self.set_instruction("Scanning… Please hold still", scanning=True)

        frame = self.last_frame_bgr.copy()
        max_price = get_max_price_per_kg()

        self.worker = OfflineScanWorker(
            detector=self.detector,
            frame_bgr=frame,
            yolo_result=None,
            conf=self.conf,
            max_price_per_kg=max_price
        )
        self.worker.finished.connect(self.on_scan_done)
        self.worker.failed.connect(self.on_scan_failed)
        self.worker.start()

    def on_scan_done(self, tray_avg, tray_grade, price_per_kg, pdf_path, kernel_results, annotated_image):

        # Restore live detection if it was previously enabled
        if hasattr(self, '_live_was_enabled') and self._live_was_enabled:
            self.live_detection_enabled = True
            self.run_live_detection()

        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)

        detected = sum(
            1 for k in kernel_results if k.get("grade") or k.get("has_normal", False)
        )

        if not pdf_path and not kernel_results:
            QMessageBox.warning(
                self,
                "Scan Failed",
                "No peanut kernels detected.\nTry again with better lighting or positioning."
            )
            return

        # Count defects and grades
        defect_counts = {}
        class_counts = {}
        for k in (kernel_results or []):
            g = k.get("grade", "Unknown")
            class_counts[g] = class_counts.get(g, 0) + 1
            for d in k.get("defects", []):
                label = d.get("label", "").lower()
                if label:
                    defect_counts[label] = defect_counts.get(label, 0) + 1

        defect_lines = [f"{k}:{v}" for k, v in defect_counts.items()]
        grade_lines = [f"{k}:{v}" for k, v in class_counts.items()]

        max_price = get_max_price_per_kg()

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
            if success:
                self.printer_status_changed.emit("Ready", True)
            else:
                self.printer_status_changed.emit("Not Connected", False)
        except Exception as e:
            print(f"Ticket printing error: {e}")
            self.printer_status_changed.emit("Error", False)

        # Show summary
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
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

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Scan Complete")
        msg_box.setText(summary_msg)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStandardButtons(QMessageBox.Ok)
        details_btn = msg_box.addButton("View Details", QMessageBox.ActionRole)
        msg_box.setFixedSize(400, 300)
        msg_box.exec_()

        #Pass the annotated image to the detailed report
        if msg_box.clickedButton() == details_btn:
            self.show_full_report(date_str, time_str, max_price, defect_lines,
                                  grade_lines, detected, tray_avg, tray_grade,
                                  price_per_kg, pdf_path, annotated_image)

    def show_full_report(self, date_str, time_str, max_price, defect_lines,
                         grade_lines, detected, tray_avg, tray_grade,
                         price_per_kg, pdf_path, annotated_image):
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QScrollArea, QWidget
        from PyQt5.QtGui import QPixmap, QImage

        dialog = QDialog(self)
        dialog.setWindowTitle("Detailed Scan Report")
        dialog.resize(1024, 550)
        dialog.setMinimumSize(800, 500)

        # Main layout for the dialog (holds the scroll area and close button)
        main_layout = QVBoxLayout(dialog)

        # Scroll area that contains the entire content (image + report)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # Container widget that will hold the image and report
        container = QWidget()
        scroll_area.setWidget(container)

        # Vertical layout inside the container
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)

        # ---- Image section ----
        if annotated_image is not None:
            # Convert BGR to RGB
            rgb = cv2.cvtColor(annotated_image, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            # Scale down if too large to keep a reasonable size, but still scrollable if needed
            max_width = 800
            max_height = 600
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(max_width, max_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            label_img = QLabel()
            label_img.setPixmap(pixmap)
            label_img.setAlignment(Qt.AlignCenter)
            label_img.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            container_layout.addWidget(label_img)
        else:
            label_img = QLabel("No image available")
            label_img.setAlignment(Qt.AlignCenter)
            label_img.setMinimumHeight(200)
            container_layout.addWidget(label_img)

        # ---- Report text section ----
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMinimumHeight(300)  # Ensure text area has enough space
        container_layout.addWidget(text_edit)

        # Build HTML (same as before)
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

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        close_btn.setFixedSize(100, 30)
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        dialog.exec_()

    def on_scan_failed(self, msg: str):
        if hasattr(self, '_live_was_enabled') and self._live_was_enabled:
            self.live_detection_enabled = True
            self.run_live_detection()

        self.scan.setEnabled(True)
        self.scan.setText("Scan")
        self.set_instruction("Position Tray then Click Scan", scanning=False)
        QMessageBox.critical(self, "Offline Detection Error", msg)
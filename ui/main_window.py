# ui/main_window.py
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QLabel,
    QHBoxLayout, QVBoxLayout, QStackedWidget,
    QSpacerItem, QSizePolicy
)
from PyQt5.QtGui import QIcon
from datetime import datetime

from camera.camera_manager import release_camera
from ui.home_page import HomePage
from ui.scanner_page import ScannerPage
from ui.history_page import HistoryPage
from ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mani-to-Money")
        self.setWindowIcon(QIcon("assets/mani.png"))
        self.setFixedSize(1024, 550)
        self.setStyleSheet("background:#E6D3A3;")

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        # -------- Side Panel --------
        side_container = QWidget()
        side_container.setFixedWidth(240)
        side_container.setObjectName("SidePanel")

        side_layout = QVBoxLayout(side_container)
        side_layout.setContentsMargins(15, 15, 15, 15)
        side_layout.setSpacing(18)

        # Top spacer -> keeps buttons vertically centered
        side_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.btn_home = QPushButton("Home")
        self.btn_scan = QPushButton("Scanner")
        self.btn_hist = QPushButton("History")
        self.btn_settings = QPushButton("Settings")

        self.btn_home.setIcon(QIcon("assets/house.png"))
        self.btn_scan.setIcon(QIcon("assets/scan.png"))
        self.btn_hist.setIcon(QIcon("assets/file.png"))
        self.btn_settings.setIcon(QIcon("assets/gear.png"))

        self.btn_home.setObjectName("navBtn")
        self.btn_scan.setObjectName("navBtn")
        self.btn_hist.setObjectName("navBtn")
        self.btn_settings.setObjectName("navBtn")

        for btn in (self.btn_home, self.btn_scan, self.btn_hist, self.btn_settings):
            btn.setIconSize(QSize(24, 24))
            btn.setLayoutDirection(Qt.LeftToRight)
            btn.setFixedSize(190, 70)
            btn.setCursor(Qt.PointingHandCursor)

        side_container.setStyleSheet("""
        QWidget#SidePanel {
            background: #C9A66B; /* almond */
        }

        QPushButton#navBtn {
            background: #6F4E37;
            color: #FFF8EE;
            font-size: 16px;
            font-weight: 650;
            border: none;
            border-radius: 14px;
            padding: 12px 14px;
            text-align: left;
        }

        QPushButton#navBtn:hover {
            background: #5C4033;
        }

        QPushButton#navBtn[active="true"] {
            background: #7A8F3A;
            color: #FFFDF5;
        }
        QPushButton#navBtn[active="true"]:hover {
            background: #6B8032;
        }
        """)

        side_layout.addWidget(self.btn_home)
        side_layout.addWidget(self.btn_scan)
        side_layout.addWidget(self.btn_hist)
        side_layout.addWidget(self.btn_settings)

        # Spacer pushes the status labels to the bottom
        side_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # -------- Camera Status --------
        self.cam_status = QLabel("Camera: Idle")
        self.cam_status.setAlignment(Qt.AlignCenter)
        self.cam_status.setFixedHeight(32)
        self.cam_status.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 10px;
                border-radius: 10px;
                background: #616161;
            }
        """)

        # -------- Printer Status --------
        self.printer_status = QLabel("🖨️ Printer: Checking...")
        self.printer_status.setAlignment(Qt.AlignCenter)
        self.printer_status.setFixedHeight(32)
        self.printer_status.setStyleSheet("""
            QLabel {
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 10px;
                border-radius: 10px;
                background: #ff9800;
            }
        """)

        # -------- Date & Time --------
        self.datetime_label = QLabel()
        self.datetime_label.setAlignment(Qt.AlignCenter)
        self.datetime_label.setFixedHeight(50)
        self.datetime_label.setStyleSheet("""
            QLabel {
                color: #2e2e2e;
                font-weight: bold;
                font-size: 15px;
                background: transparent;
            }
        """)

        # Timer for live clock
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_datetime)
        self.clock_timer.start(1000)  # update every second
        self.update_datetime()  # initialize immediately

        # Add status widgets to side panel (in order: datetime, camera, printer)
        side_layout.addWidget(self.datetime_label)
        side_layout.addWidget(self.cam_status)
        side_layout.addWidget(self.printer_status)

        root.addWidget(side_container)

        # -------- Pages --------
        self.stack = QStackedWidget()

        self.home = HomePage()
        self.scanner = ScannerPage()
        self.history = HistoryPage()
        self.settings = SettingsPage()

        # Connect settings page signal to handle camera restart
        self.settings.settings_changed.connect(self.on_settings_changed)

        # Connect scanner page signal to update printer status
        self.scanner.printer_status_changed.connect(self.set_printer_status)

        self.stack.addWidget(self.home)  # index 0
        self.stack.addWidget(self.scanner)  # index 1
        self.stack.addWidget(self.history)  # index 2
        self.stack.addWidget(self.settings)  # index 3

        root.addWidget(self.stack, stretch=1)

        # -------- Navigation --------
        self.btn_home.clicked.connect(lambda: self.switch_page(0))
        self.btn_scan.clicked.connect(lambda: self.switch_page(1))
        self.btn_hist.clicked.connect(lambda: self.switch_page(2))
        self.btn_settings.clicked.connect(lambda: self.switch_page(3))

        # Start on Home page
        self.switch_page(0)

        # Check printer status after UI is loaded
        QTimer.singleShot(1000, self.check_printer_status)

    def update_datetime(self):
        now = datetime.now()
        date_str = now.strftime("%B %d, %Y")  # February 18, 2026
        time_str = now.strftime("%I:%M:%S %p")  # 12-hour format with AM/PM

        if time_str.startswith("0"):
            time_str = time_str[1:]

        self.datetime_label.setText(f"{date_str}\n{time_str}")

    def set_active_nav(self, active_btn):
        for btn in (self.btn_home, self.btn_scan, self.btn_hist, self.btn_settings):
            btn.setProperty("active", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        active_btn.setProperty("active", True)
        active_btn.style().unpolish(active_btn)
        active_btn.style().polish(active_btn)

    def set_camera_status(self, state: str):
        state = (state or "").strip().lower()

        if state == "active":
            text = "Camera: Active"
            bg = "#2e7d32"  # green
        elif state in ("not found", "error", "missing"):
            text = "Camera: Not Found"
            bg = "#c62828"  # red
        else:
            text = "Camera: Idle"
            bg = "#616161"  # gray

        self.cam_status.setText(text)
        self.cam_status.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 10px;
                border-radius: 10px;
                background: {bg};
            }}
        """)

    def set_printer_status(self, status: str, connected: bool = True):
        """
        Update printer status display

        Args:
            status: Status text to display
            connected: True if printer is connected/ready, False if error
        """
        if connected:
            bg = "#2e7d32"  # green
            icon = "🖨️"
        else:
            bg = "#c62828"  # red
            icon = "⚠️"

        self.printer_status.setText(f"{icon} Printer: {status}")
        self.printer_status.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 6px 10px;
                border-radius: 10px;
                background: {bg};
            }}
        """)

    def check_printer_status(self):
        """Check printer connection status"""
        try:
            from utils.ticket import check_printer_connection
            connected = check_printer_connection()
            if connected:
                self.set_printer_status("Ready", True)
            else:
                self.set_printer_status("Not Connected", False)
        except Exception as e:
            print(f"Printer check error: {e}")
            self.set_printer_status("Error", False)

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)

        # nav highlight
        if index == 0:
            self.set_active_nav(self.btn_home)
        elif index == 1:
            self.set_active_nav(self.btn_scan)
        elif index == 2:
            self.set_active_nav(self.btn_hist)
        elif index == 3:
            self.set_active_nav(self.btn_settings)

        # camera lifecycle + status
        if index == 1:
            ok = self.scanner.start_camera()  # returns True/False
            self.set_camera_status("active" if ok else "not found")
        else:
            self.scanner.stop_camera()
            self.set_camera_status("idle")

        # history refresh
        if index == 2:
            self.history.refresh()

        # Check printer status on every page change
        QTimer.singleShot(100, self.check_printer_status)

    def closeEvent(self, event):
        try:
            self.scanner.stop_camera()
        finally:
            release_camera()
        event.accept()

    def on_settings_changed(self):
        """Handle settings changes - restart camera if on scanner page"""
        if self.stack.currentIndex() == 1:
            self.scanner.stop_camera()
            QTimer.singleShot(500, lambda: self.scanner.start_camera())
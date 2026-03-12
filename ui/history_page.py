import os
from PyQt5.QtWidgets import (
    QWidget, QListWidget, QListWidgetItem,
    QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
)
import time
from PyQt5.QtCore import pyqtSignal
from utils.app_settings import get_history_auto_purge, get_history_keep_days
from utils.file_utils import project_path,pretty_scan_name
from utils.open_file import open_file
from PyQt5.QtWidgets import QScroller



class HistoryPage(QWidget):
    backRequested = pyqtSignal()

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # -------- Receipt List --------
        self.list_widget = QListWidget()
        QScroller.grabGesture(
            self.list_widget.viewport(),
            QScroller.LeftMouseButtonGesture
        )

        self.list_widget.setStyleSheet("""
            QListWidget {
                background: #f5eedc;
                border-radius: 10px;
                padding: 10px;
                font-size: 18px;
            }
            QListWidget::item {
                padding: 16px;
                margin: 6px;
                border-radius: 8px;
                background: #ffffff;
            }
            QListWidget::item:selected {
                background: #cfe8ff;
                color: #111;
            }
        """)
        root.addWidget(self.list_widget, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        self.open_btn = QPushButton("Open Receipt")
        self.open_btn.setFixedSize(180, 48)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background:#000;
                color:white;
                font-size:16px;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover { background:#4CAF50; }
        """)

        bottom_row.addWidget(self.open_btn)
        root.addLayout(bottom_row)

        # -------- Data --------
        self.folder = project_path("receipts")
        self.files = []
        self.current_path = None

        # -------- Signals --------
        self.list_widget.currentRowChanged.connect(self.on_select_row)
        self.open_btn.clicked.connect(self.open_current)

        self.refresh()

    def refresh(self):
        self.list_widget.clear()
        self.files.clear()
        self.current_path = None

        # -------- Auto purge old receipts --------
        if get_history_auto_purge() and os.path.exists(self.folder):
            keep_days = get_history_keep_days()
            cutoff = time.time() - (keep_days * 24 * 60 * 60)

            for fname in os.listdir(self.folder):
                if not fname.lower().endswith(".pdf"):
                    continue
                full = os.path.join(self.folder, fname)
                try:
                    if os.path.getmtime(full) < cutoff:
                        os.remove(full)
                except Exception:
                    pass

        if not os.path.exists(self.folder):
            self.list_widget.addItem("No receipts found")
            self.list_widget.setEnabled(False)
            self.open_btn.setEnabled(False)
            return

        pdfs = sorted(
            [f for f in os.listdir(self.folder) if f.lower().endswith(".pdf")],
            reverse=True
        )

        if not pdfs:
            self.list_widget.addItem("No receipts found")
            self.list_widget.setEnabled(False)
            self.open_btn.setEnabled(False)
            return

        self.list_widget.setEnabled(True)
        self.open_btn.setEnabled(True)

        for fname in pdfs:
            full = os.path.join(self.folder, fname)
            self.files.append(full)

            label = pretty_scan_name(fname)
            item = QListWidgetItem(label)
            item.setToolTip(fname)
            self.list_widget.addItem(item)

        self.list_widget.setCurrentRow(0)

    def on_select_row(self, row: int):
        if 0 <= row < len(self.files):
            self.current_path = self.files[row]
        else:
            self.current_path = None

    def open_current(self):
        if not self.current_path:
            QMessageBox.information(self, "Open Receipt", "No receipt selected.")
            return

        open_file(self.current_path)

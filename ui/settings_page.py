# ui/settings_page.py
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QDoubleSpinBox, QPushButton, QMessageBox, QCheckBox, QSpinBox
)

from PyQt5.QtCore import Qt

from utils.app_settings import (
    get_max_price_per_kg, set_max_price_per_kg,
    get_history_auto_purge, set_history_auto_purge,
    get_history_keep_days, set_history_keep_days
)


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignTop)

        desc = QLabel("Adjust Price")
        desc.setStyleSheet("QLabel { font-size: 25px; font-weight: 700;}")
        root.addWidget(desc)

        row = QHBoxLayout()
        row.setSpacing(12)

        label = QLabel("Max price per kg (₱):")
        label.setStyleSheet("QLabel { font-size: 16px; font-weight: 700; }")

        self.spin = QDoubleSpinBox()
        self.spin.setRange(1.0, 100000.0)
        self.spin.setDecimals(2)
        self.spin.setSingleStep(10.0)
        self.spin.setValue(get_max_price_per_kg())
        self.spin.setFixedWidth(220)
        self.spin.setStyleSheet("""
            QDoubleSpinBox {
                background: white;
                padding: 8px 10px;
                border-radius: 10px;
                font-size: 16px;
            }
        """)

        row.addWidget(label)
        row.addWidget(self.spin)
        row.addStretch()
        root.addLayout(row)

        # -------- History Settings --------
        hist_title = QLabel("History")
        hist_title.setStyleSheet("QLabel { font-size: 25px; font-weight: 800; margin-top: 10px; }")
        root.addWidget(hist_title)

        self.chk_purge = QCheckBox("Auto-purge old receipts")
        self.chk_purge.setChecked(get_history_auto_purge())
        self.chk_purge.setStyleSheet("QCheckBox { font-size: 16px; font-weight: 650; }")
        root.addWidget(self.chk_purge)

        days_row = QHBoxLayout()
        days_row.setSpacing(12)

        days_label = QLabel("Keep receipts for (days):")
        days_label.setStyleSheet("QLabel { font-size: 16px; font-weight: 700; }")

        self.keep_days = QSpinBox()
        self.keep_days.setRange(1, 3650)
        self.keep_days.setValue(get_history_keep_days())
        self.keep_days.setFixedWidth(120)
        self.keep_days.setStyleSheet("""
            QSpinBox {
                background: white;
                padding: 8px 10px;
                border-radius: 10px;
                font-size: 16px;
            }
        """)

        days_row.addWidget(days_label)
        days_row.addWidget(self.keep_days)
        days_row.addStretch()
        root.addLayout(days_row)

        def _sync_days_enabled():
            self.keep_days.setEnabled(self.chk_purge.isChecked())

        self.chk_purge.stateChanged.connect(_sync_days_enabled)
        _sync_days_enabled()

        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedSize(160, 55)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background:#4CAF50;
                color:white;
                font-size:16px;
                font-weight:800;
                border-radius:12px;
            }
            QPushButton:hover { background:#388E3C; }
        """)
        self.save_btn.clicked.connect(self.on_save)
        # Push everything above upward
        root.addStretch()

        # Bottom row for Save button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()  # pushes button to right
        bottom_row.addWidget(self.save_btn)

        root.addLayout(bottom_row)

    def on_save(self):
        val = float(self.spin.value())
        set_max_price_per_kg(val)

        set_history_auto_purge(self.chk_purge.isChecked())
        set_history_keep_days(int(self.keep_days.value()))

        QMessageBox.information(
            self,
            "Saved",
            f"Max price per kg set to ₱{val:.2f}.\n"
            f"Auto-purge: {'ON' if self.chk_purge.isChecked() else 'OFF'}\n"
            f"Keep days: {int(self.keep_days.value())}"
        )


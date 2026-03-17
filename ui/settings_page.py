import sys
import platform
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QCheckBox,
    QDialog, QGridLayout, QLineEdit, QFrame,
    QScrollArea, QComboBox, QSlider, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal

from utils.app_settings import (
    get_max_price_per_kg, set_max_price_per_kg,
    get_history_auto_purge, set_history_auto_purge,
    get_history_keep_days, set_history_keep_days,
    validate_passcode, get_camera_settings, update_camera_settings
)


class NumberKeyboardDialog(QDialog):
    def __init__(self, value="", allow_decimal=True, parent=None, password_mode=False):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.allow_decimal = allow_decimal
        self.password_mode = password_mode
        self.real_value = str(value)

        self.setWindowTitle("Enter Value")
        self.setModal(True)
        self.setFixedSize(450, 550)

        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 20px;
            }
            QLineEdit {
                background-color: #f8f9fa;
                color: #2c3e50;
                border: 2px solid #e0e0e0;
                border-radius: 15px;
                padding: 15px;
                font-size: 28px;
                font-weight: bold;
                min-height: 50px;
            }
            QPushButton {
                background-color: #4a90e2;
                color: #ffffff;
                border: none;
                border-radius: 15px;
                font-size: 24px;
                font-weight: bold;
                min-height: 70px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5aa0f2;
            }
            QPushButton:pressed {
                background-color: #3a80d2;
            }
            QPushButton:disabled {
                background-color: #e0e0e0;
                color: #a0a0a0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Display
        self.display = QLineEdit()
        self.display.setAlignment(Qt.AlignRight)
        self.display.setReadOnly(True)
        self.display.setMinimumHeight(60)
        layout.addWidget(self.display)
        self._refresh_display()

        # Number grid
        grid = QGridLayout()
        grid.setSpacing(10)

        buttons = [
            ("7", 0, 0), ("8", 0, 1), ("9", 0, 2),
            ("4", 1, 0), ("5", 1, 1), ("6", 1, 2),
            ("1", 2, 0), ("2", 2, 1), ("3", 2, 2),
            ("0", 3, 0), (".", 3, 1), ("⌫", 3, 2),
        ]

        for text, row, col in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(lambda _, t=text: self.handle_button(t))

            if text == "." and not self.allow_decimal:
                btn.setEnabled(False)

            grid.addWidget(btn, row, col)

        layout.addLayout(grid)

        # Bottom buttons
        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        clear_btn = QPushButton("Clear")
        clear_btn.setMinimumHeight(60)
        clear_btn.clicked.connect(self.clear_text)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumHeight(60)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("OK")
        ok_btn.setMinimumHeight(60)
        ok_btn.clicked.connect(self.accept)

        bottom.addWidget(clear_btn)
        bottom.addWidget(cancel_btn)
        bottom.addWidget(ok_btn)
        layout.addLayout(bottom)

    def _refresh_display(self):
        if self.password_mode:
            self.display.setText("*" * len(self.real_value))
        else:
            self.display.setText(self.real_value)

    def handle_button(self, text):
        current = self.real_value

        if text == "⌫":
            self.real_value = current[:-1]
            self._refresh_display()
            return

        if text == ".":
            if not self.allow_decimal or "." in current:
                return
            if not current:
                current = "0"
            self.real_value = current + "."
            self._refresh_display()
            return

        if text.isdigit():
            if "." in current:
                decimal_part = current.split(".", 1)[1]
                if len(decimal_part) >= 2:
                    return

        self.real_value = current + text
        self._refresh_display()

    def clear_text(self):
        self.real_value = ""
        self._refresh_display()

    def get_value(self):
        return self.real_value.strip()


class SettingsCard(QFrame):
    """Reusable card widget for settings sections"""

    def __init__(self, title):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            SettingsCard {
                background-color: #ffffff;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
                padding: 15px;
                margin: 0px;
            }
            QLabel {
                background-color: transparent;
                color: #2c3e50;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-size: 16px;
                font-weight: bold;
                padding: 0px;
                margin: 0px;
                background-color: transparent;
            }
        """)
        layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(10)
        self.content_layout.setContentsMargins(0, 5, 0, 0)
        layout.addLayout(self.content_layout)

    def addWidget(self, widget):
        self.content_layout.addWidget(widget)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)


class ClickableNumberField(QLineEdit):
    def __init__(self, value="", allow_decimal=True, parent=None):
        super().__init__(parent)
        self.allow_decimal = allow_decimal
        self.setText(str(value))
        self.setReadOnly(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignLeft)
        self.setMinimumHeight(35)
        self.setMaximumWidth(150)

        self.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #2c3e50;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 5px 10px;
                font-size: 14px;
            }
            QLineEdit:hover {
                border: 1px solid #4a90e2;
                background-color: #ffffff;
            }
        """)

    def mousePressEvent(self, event):
        self.open_keyboard()

    def open_keyboard(self):
        dlg = NumberKeyboardDialog(
            value=self.text(),
            allow_decimal=self.allow_decimal,
            parent=self.window()
        )
        if dlg.exec_():
            text = dlg.get_value()
            if not text:
                return

            try:
                if self.allow_decimal:
                    value = float(text)
                    self.setText(f"{value:.2f}")
                else:
                    value = int(text)
                    self.setText(str(value))
            except ValueError:
                pass

    def get_numeric_value(self):
        text = self.text().strip()
        if self.allow_decimal:
            return float(text) if text else 0.0
        return int(text) if text else 0

    def set_numeric_value(self, value):
        if self.allow_decimal:
            self.setText(f"{float(value):.2f}")
        else:
            self.setText(str(int(value)))


class SettingsPage(QWidget):
    settings_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Set background color for the whole page
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                color: #2c3e50;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #4a90e2;
                color: white;
            }
            QLabel {
                background-color: transparent;
                color: #2c3e50;
            }
            QCheckBox {
                background-color: transparent;
                color: #2c3e50;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border: 1px solid #4a90e2;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 5px;
                min-height: 25px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #e0e0e0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4a90e2;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabWidget { background-color: transparent; }")

        # General tab
        general_tab = QWidget()
        general_tab.setStyleSheet("background-color: transparent;")
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(0, 10, 0, 0)
        general_layout.setSpacing(10)

        # Price Settings Card
        price_card = SettingsCard("Price Settings")
        price_row = QHBoxLayout()
        price_row.setSpacing(10)

        price_label = QLabel("Max Price per kg:")
        price_label.setStyleSheet("font-size: 13px; background-color: transparent;")
        price_label.setMinimumWidth(120)

        self.spin = ClickableNumberField(
            value=f"{get_max_price_per_kg():.2f}",
            allow_decimal=True
        )

        currency_label = QLabel("₱")
        currency_label.setStyleSheet("color: #4a90e2; font-size: 14px; background-color: transparent;")

        price_row.addWidget(price_label)
        price_row.addWidget(currency_label)
        price_row.addWidget(self.spin)
        price_row.addStretch()
        price_card.addLayout(price_row)
        general_layout.addWidget(price_card)

        # History Settings Card
        history_card = SettingsCard("History Settings")

        # Auto-purge checkbox
        self.chk_purge = QCheckBox("Auto-cleanup old receipts")
        self.chk_purge.setChecked(get_history_auto_purge())
        self.chk_purge.setStyleSheet("font-size: 13px; background-color: transparent;")
        history_card.addWidget(self.chk_purge)

        # Keep days row
        days_row = QHBoxLayout()
        days_row.setSpacing(10)

        days_label = QLabel("Keep for:")
        days_label.setMinimumWidth(60)
        days_label.setStyleSheet("background-color: transparent;")

        self.keep_days = ClickableNumberField(
            value=str(get_history_keep_days()),
            allow_decimal=False
        )

        days_unit = QLabel("days")
        days_unit.setStyleSheet("background-color: transparent;")

        days_row.addWidget(days_label)
        days_row.addWidget(self.keep_days)
        days_row.addWidget(days_unit)
        days_row.addStretch()

        def _sync_days_enabled():
            self.keep_days.setEnabled(self.chk_purge.isChecked())

        self.chk_purge.stateChanged.connect(_sync_days_enabled)
        _sync_days_enabled()

        history_card.addLayout(days_row)
        general_layout.addWidget(history_card)
        general_layout.addStretch()

        # Camera tab
        camera_tab = QWidget()
        camera_tab.setStyleSheet("background-color: transparent;")
        camera_layout = QVBoxLayout(camera_tab)
        camera_layout.setContentsMargins(0, 10, 0, 0)
        camera_layout.setSpacing(10)
        camera_layout.addWidget(self.create_camera_tab())
        camera_layout.addStretch()

        # Add tabs
        self.tabs.addTab(general_tab, "General")
        self.tabs.addTab(camera_tab, "Camera")

        main_layout.addWidget(self.tabs)

        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setFixedSize(150, 35)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aa0f2;
            }
        """)
        self.save_btn.clicked.connect(self.on_save)

        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

    def on_save(self):
        try:
            # Store old values for rollback
            old_price = get_max_price_per_kg()
            old_keep_days = get_history_keep_days()
            old_auto_purge = get_history_auto_purge()

            # Passcode dialog
            dlg = NumberKeyboardDialog(
                value="",
                allow_decimal=False,
                parent=self,
                password_mode=True
            )
            dlg.setWindowTitle("Enter Passcode")

            if not dlg.exec_():
                # Cancelled - revert UI
                self.spin.set_numeric_value(old_price)
                self.keep_days.set_numeric_value(old_keep_days)
                self.chk_purge.setChecked(old_auto_purge)
                return

            password = dlg.get_value()

            if not validate_passcode(password):
                # Wrong passcode - revert UI
                self.spin.set_numeric_value(old_price)
                self.keep_days.set_numeric_value(old_keep_days)
                self.chk_purge.setChecked(old_auto_purge)
                QMessageBox.warning(
                    self,
                    "Access Denied",
                    "Incorrect passcode. Changes were not saved."
                )
                return

            # Save general settings
            val = self.spin.get_numeric_value()
            keep_days = self.keep_days.get_numeric_value()
            auto_purge = self.chk_purge.isChecked()

            set_max_price_per_kg(val)
            set_history_auto_purge(auto_purge)
            set_history_keep_days(keep_days)

            # --- Camera settings ---
            # Verify all required widgets exist
            required_attrs = [
                'camera_res', 'camera_fps',
                'camera_hflip', 'camera_vflip'
            ]
            missing = [attr for attr in required_attrs if not hasattr(self, attr)]
            if missing:
                raise RuntimeError(f"Camera UI components missing: {missing}")

            camera_settings = {
                "resolution": self.camera_res.currentText(),
                "fps": int(self.camera_fps.currentText()),
                "hflip": self.camera_hflip.isChecked(),
                "vflip": self.camera_vflip.isChecked()
            }
            update_camera_settings(camera_settings)

            # Notify that settings have changed (e.g., to restart camera)
            self.settings_changed.emit()

            QMessageBox.information(self, "Success", "Settings saved successfully.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred while saving:\n{str(e)}"
            )

    def create_camera_tab(self):
        """Create camera settings tab with basic controls only"""

        camera_card = SettingsCard("Camera Settings")

        camera_settings = get_camera_settings()

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # ===== BASIC CONTROLS =====
        enabled_grid = QGridLayout()
        enabled_grid.setColumnStretch(1, 1)
        enabled_grid.setVerticalSpacing(15)
        enabled_grid.setHorizontalSpacing(15)

        combo_style = """
            QComboBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                min-height: 30px;
                font-size: 13px;
            }
        """

        # Resolution
        enabled_grid.addWidget(QLabel("Resolution:"), 0, 0)
        self.camera_res = QComboBox()
        self.camera_res.addItems(["640x480", "800x600", "1024x768", "1280x720", "1920x1080"])
        self.camera_res.setCurrentText(camera_settings.get("resolution", "1280x720"))
        self.camera_res.setMaximumWidth(180)
        self.camera_res.setStyleSheet(combo_style)
        enabled_grid.addWidget(self.camera_res, 0, 1)

        # FPS
        enabled_grid.addWidget(QLabel("Frame Rate:"), 1, 0)
        self.camera_fps = QComboBox()
        self.camera_fps.addItems(["15", "30", "60"])
        self.camera_fps.setCurrentText(str(camera_settings.get("fps", 30)))
        self.camera_fps.setMaximumWidth(180)
        self.camera_fps.setStyleSheet(combo_style)
        enabled_grid.addWidget(self.camera_fps, 1, 1)

        # Flip
        enabled_grid.addWidget(QLabel("Flip:"), 2, 0)
        flip_widget = QWidget()
        flip_layout = QHBoxLayout(flip_widget)
        flip_layout.setContentsMargins(0, 0, 0, 0)
        flip_layout.setSpacing(20)

        self.camera_hflip = QCheckBox("Horizontal")
        self.camera_hflip.setChecked(camera_settings.get("hflip", False))
        self.camera_hflip.setStyleSheet("QCheckBox { font-size: 13px; }")
        flip_layout.addWidget(self.camera_hflip)

        self.camera_vflip = QCheckBox("Vertical")
        self.camera_vflip.setChecked(camera_settings.get("vflip", False))
        self.camera_vflip.setStyleSheet("QCheckBox { font-size: 13px; }")
        flip_layout.addWidget(self.camera_vflip)

        flip_layout.addStretch()
        enabled_grid.addWidget(flip_widget, 2, 1)

        main_layout.addLayout(enabled_grid)

        # Add some spacing
        main_layout.addSpacing(20)

        # NOTE
        note = QLabel("Note: Changes apply after camera restart.")
        note.setStyleSheet("color:#808080;font-size:12px;font-style:italic;padding:10px 0px;")
        note.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(note)

        # Add stretch to push content up
        main_layout.addStretch()

        camera_card.addLayout(main_layout)

        return camera_card
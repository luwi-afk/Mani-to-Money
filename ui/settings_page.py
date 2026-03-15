# ui/settings_page.py
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox, QCheckBox,
    QDialog, QGridLayout, QLineEdit, QFrame,
    QScrollArea
)
from PyQt5.QtCore import Qt

from utils.app_settings import (
    get_max_price_per_kg, set_max_price_per_kg,
    get_history_auto_purge, set_history_auto_purge,
    get_history_keep_days, set_history_keep_days,
    validate_passcode
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
                border-radius: 15px;
                border: 1px solid #e0e0e0;
                padding: 20px;
                margin: 5px;
            }
            SettingsCard:hover {
                border: 1px solid #4a90e2;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title with white background
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                color: #2c3e50;
                font-size: 20px;
                font-weight: bold;
                padding: 5px 0px;
                margin: 0px;
                border-bottom: 2px solid #4a90e2;
            }
        """)
        layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(15)
        self.content_layout.setContentsMargins(0, 10, 0, 0)
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
        self.setMinimumHeight(45)
        self.setMaximumWidth(200)

        self.setStyleSheet("""
            QLineEdit {
                background-color: #f8f9fa;
                color: #2c3e50;
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                padding: 10px 15px;
                font-size: 16px;
                font-weight: 600;
            }
            QLineEdit:hover {
                border: 2px solid #4a90e2;
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
    def __init__(self):
        super().__init__()

        # Set page background
        self.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
            }
            QLabel {
                background-color: transparent;
                color: #2c3e50;
            }
            QCheckBox {
                background-color: transparent;
                color: #2c3e50;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border: 2px solid #4a90e2;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header
        header = QLabel("Settings")
        header.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #2c3e50;
                font-size: 36px;
                font-weight: bold;
                padding-bottom: 20px;
            }
        """)
        header.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(header)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
        """)

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: transparent;")
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # Price Settings Card
        price_card = SettingsCard("Price Settings")

        price_row = QHBoxLayout()
        price_row.setSpacing(20)

        price_label = QLabel("Maximum Price per Kilogram:")
        price_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #2c3e50;
                font-size: 16px;
                font-weight: 500;
            }
        """)
        price_label.setMinimumWidth(250)

        self.spin = ClickableNumberField(
            value=f"{get_max_price_per_kg():.2f}",
            allow_decimal=True
        )

        currency_label = QLabel("₱")
        currency_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #4a90e2;
                font-size: 18px;
                font-weight: bold;
            }
        """)

        price_row.addWidget(price_label)
        price_row.addWidget(currency_label)
        price_row.addWidget(self.spin)
        price_row.addStretch()

        price_card.addLayout(price_row)
        scroll_layout.addWidget(price_card)

        # History Settings Card
        history_card = SettingsCard("History Settings")

        # Auto-purge checkbox
        self.chk_purge = QCheckBox("Enable automatic history cleanup")
        self.chk_purge.setChecked(get_history_auto_purge())
        self.chk_purge.setStyleSheet("""
            QCheckBox {
                background-color: transparent;
                color: #2c3e50;
                font-size: 16px;
                spacing: 10px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                background-color: #ffffff;
                border: 2px solid #e0e0e0;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a90e2;
                border: 2px solid #4a90e2;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #4a90e2;
            }
        """)
        history_card.addWidget(self.chk_purge)

        # Keep days row
        days_row = QHBoxLayout()
        days_row.setSpacing(20)

        days_label = QLabel("Keep receipts for:")
        days_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #2c3e50;
                font-size: 16px;
                font-weight: 500;
            }
        """)
        days_label.setMinimumWidth(150)

        self.keep_days = ClickableNumberField(
            value=str(get_history_keep_days()),
            allow_decimal=False
        )

        days_unit = QLabel("days")
        days_unit.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #2c3e50;
                font-size: 16px;
                font-weight: 500;
            }
        """)

        days_row.addWidget(days_label)
        days_row.addWidget(self.keep_days)
        days_row.addWidget(days_unit)
        days_row.addStretch()

        history_card.addLayout(days_row)

        # Enable/disable based on checkbox
        def _sync_days_enabled():
            self.keep_days.setEnabled(self.chk_purge.isChecked())
            if not self.chk_purge.isChecked():
                self.keep_days.setStyleSheet("""
                    QLineEdit {
                        background-color: #f0f0f0;
                        color: #a0a0a0;
                        border: 2px solid #e0e0e0;
                        border-radius: 10px;
                        padding: 10px 15px;
                        font-size: 16px;
                        font-weight: 600;
                    }
                """)
            else:
                self.keep_days.setStyleSheet("""
                    QLineEdit {
                        background-color: #f8f9fa;
                        color: #2c3e50;
                        border: 2px solid #e0e0e0;
                        border-radius: 10px;
                        padding: 10px 15px;
                        font-size: 16px;
                        font-weight: 600;
                    }
                    QLineEdit:hover {
                        border: 2px solid #4a90e2;
                        background-color: #ffffff;
                    }
                """)

        self.chk_purge.stateChanged.connect(_sync_days_enabled)
        _sync_days_enabled()

        scroll_layout.addWidget(history_card)

        # Add stretch at the bottom
        scroll_layout.addStretch()

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Save button
        button_container = QWidget()
        button_container.setStyleSheet("background-color: transparent;")
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setFixedSize(250, 60)
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: #ffffff;
                border: none;
                border-radius: 15px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aa0f2;
            }
            QPushButton:pressed {
                background-color: #3a80d2;
            }
        """)
        self.save_btn.clicked.connect(self.on_save)

        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addStretch()

        main_layout.addWidget(button_container)

    def on_save(self):
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

        # Save settings
        val = self.spin.get_numeric_value()
        keep_days = self.keep_days.get_numeric_value()
        auto_purge = self.chk_purge.isChecked()

        set_max_price_per_kg(val)
        set_history_auto_purge(auto_purge)
        set_history_keep_days(keep_days)

        QMessageBox.information(
            self,
            "Settings Saved",
            f"✓ Maximum price: ₱{val:.2f}/kg\n"
            f"✓ Auto-cleanup: {'ON' if auto_purge else 'OFF'}\n"
            f"✓ Keep for: {keep_days} days"
        )
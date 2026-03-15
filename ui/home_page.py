from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor

from utils.file_utils import project_path


class HomePage(QWidget):
    def __init__(self):
        super().__init__()

        self.setStyleSheet("""
            QWidget {
                background: #e5d4a5;
            }
            QLabel {
                background: transparent;
            }
        """)

        # ---------- Main Layout ----------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(0)

        # ---------- Title Block ----------
        title = QLabel("Mani-to-Money")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(False)
        title.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: 800;
                color: #5b331d;
            }
        """)

        subtitle = QLabel("Peanut Kernel Classifier with Score-Based Pricing")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: 700;
                color: #7b5638;
            }
        """)
        subtitle.setFixedWidth(700)

        desc = QLabel(
            "A user-friendly system for classifying peanut kernels and generating fair,\n"
            "transparent pricing based on quality scores."
        )
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(False)
        desc.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                color: #6d6257;
            }
        """)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(4)
        text_wrap.addWidget(title, alignment=Qt.AlignCenter)
        text_wrap.addWidget(subtitle, alignment=Qt.AlignCenter)
        text_wrap.addWidget(desc, alignment=Qt.AlignCenter)

        text_container = QWidget()
        text_container.setLayout(text_wrap)
        text_container.setFixedWidth(760)

        layout.addWidget(text_container, alignment=Qt.AlignCenter)
        layout.addSpacing(25)

        # ---------- Logos Row ----------
        logos_layout = QHBoxLayout()
        logos_layout.setSpacing(55)
        logos_layout.setAlignment(Qt.AlignCenter)

        # CSU logo
        left_logo = QLabel()
        left_logo.setAlignment(Qt.AlignCenter)
        left_pix = QPixmap(project_path("assets", "csu.png"))
        if not left_pix.isNull():
            left_logo.setPixmap(
                left_pix.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        left_logo.setFixedSize(120, 140)

        # Mani logo
        main_logo = QLabel()
        main_logo.setAlignment(Qt.AlignCenter)
        main_pix = QPixmap(project_path("assets", "mani.png"))
        if not main_pix.isNull():
            main_logo.setPixmap(
                main_pix.scaled(210, 210, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        main_logo.setFixedSize(200, 190)

        # ICpEP logo
        right_logo = QLabel()
        right_logo.setAlignment(Qt.AlignCenter)
        right_pix = QPixmap(project_path("assets", "cpe.png"))
        if not right_pix.isNull():
            right_logo.setPixmap(
                right_pix.scaled(145, 145, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        right_logo.setFixedSize(150, 140)

        # ---------- Shadows ----------
        shadow_left = QGraphicsDropShadowEffect()
        shadow_left.setBlurRadius(28)
        shadow_left.setOffset(0, 8)
        shadow_left.setColor(QColor(0, 0, 0, 80))
        left_logo.setGraphicsEffect(shadow_left)

        shadow_main = QGraphicsDropShadowEffect()
        shadow_main.setBlurRadius(40)
        shadow_main.setOffset(0, 10)
        shadow_main.setColor(QColor(0, 0, 0, 100))
        main_logo.setGraphicsEffect(shadow_main)

        shadow_right = QGraphicsDropShadowEffect()
        shadow_right.setBlurRadius(28)
        shadow_right.setOffset(0, 8)
        shadow_right.setColor(QColor(0, 0, 0, 80))
        right_logo.setGraphicsEffect(shadow_right)

        # ---------- Vertical alignment wrappers ----------
        left_wrap = QVBoxLayout()
        left_wrap.setContentsMargins(0, 28, 0, 0)
        left_wrap.addWidget(left_logo, alignment=Qt.AlignCenter)

        center_wrap = QVBoxLayout()
        center_wrap.setContentsMargins(0, 0, 0, 0)
        center_wrap.addWidget(main_logo, alignment=Qt.AlignCenter)

        right_wrap = QVBoxLayout()
        right_wrap.setContentsMargins(0, 22, 0, 0)
        right_wrap.addWidget(right_logo, alignment=Qt.AlignCenter)

        left_container = QWidget()
        left_container.setLayout(left_wrap)

        center_container = QWidget()
        center_container.setLayout(center_wrap)

        right_container = QWidget()
        right_container.setLayout(right_wrap)

        logos_layout.addWidget(left_container)
        logos_layout.addWidget(center_container)
        logos_layout.addWidget(right_container)

        layout.addLayout(logos_layout)
        layout.addSpacing(26)

        # ---------- Footer ----------
        footer = QLabel("Efficient      •      Standardized      •      Transparent")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 700;
                color: #9d846c;
            }
        """)
        layout.addWidget(footer, alignment=Qt.AlignCenter)

        layout.addStretch(1)
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout,QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor

from utils.file_utils import project_path


class HomePage(QWidget):
    def __init__(self):
        super().__init__()

        # ---------- Layout ----------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30,10, 30, 30)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # ---------- Title ----------
        title = QLabel(
            "Mani-to-Money : Peanut Kernel Classifier with Score Based Pricing"
        )
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 34px;
                font-weight: 700;
                color: #2e2e2e;
            }
        """)


        # ---------- Logos Row ----------
        logo_row = QVBoxLayout()
        logo_row.setAlignment(Qt.AlignCenter)

        logos_layout = QHBoxLayout()
        logos_layout.setSpacing(40)
        logos_layout.setAlignment(Qt.AlignCenter)

        # CSU logo
        left_logo = QLabel()
        left_logo.setAlignment(Qt.AlignCenter)

        left_pix = QPixmap(project_path("assets", "csu.png"))
        if not left_pix.isNull():
            left_logo.setPixmap(
                left_pix.scaled(
                    120, 120,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

        # Mani logo
        main_logo = QLabel()
        main_logo.setAlignment(Qt.AlignCenter)

        main_pix = QPixmap(project_path("assets", "mani.png"))
        if not main_pix.isNull():
            main_logo.setPixmap(
                main_pix.scaled(
                    200, 200,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

        # ICpEP logo
        right_logo = QLabel()
        right_logo.setAlignment(Qt.AlignCenter)

        right_pix = QPixmap(project_path("assets", "cpe.png"))
        if not right_pix.isNull():
            right_logo.setPixmap(
                right_pix.scaled(
                    160, 150,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

        #remove bg
        left_logo.setFixedSize(left_logo.pixmap().size())
        left_logo.setStyleSheet("background: transparent;")

        main_logo.setFixedSize(main_logo.pixmap().size())
        main_logo.setStyleSheet("background: transparent;")

        right_logo.setFixedSize(right_logo.pixmap().size())
        right_logo.setStyleSheet("background: transparent;")

        #shadow main logo pop up

        shadow_side = QGraphicsDropShadowEffect()
        shadow_side.setBlurRadius(35)
        shadow_side.setOffset(0, 18)
        shadow_side.setColor(QColor(0, 0, 0, 170))
        left_logo.setGraphicsEffect(shadow_side)

        shadow_main = QGraphicsDropShadowEffect()
        shadow_main.setBlurRadius(60)
        shadow_main.setOffset(0, 18)
        shadow_main.setColor(QColor(0, 0, 0, 200))
        main_logo.setGraphicsEffect(shadow_main)

        shadow_side2 = QGraphicsDropShadowEffect()
        shadow_side2.setBlurRadius(35)
        shadow_side2.setOffset(0, 12)
        shadow_side2.setColor(QColor(0, 0, 0, 170))
        right_logo.setGraphicsEffect(shadow_side2)


        # Add to layout
        logos_layout.addWidget(left_logo)
        logos_layout.addWidget(main_logo)
        logos_layout.addWidget(right_logo)
        layout.addLayout(logos_layout)
        layout.addSpacing(25)
        layout.addWidget(title)
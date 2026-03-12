from PyQt5.QtCore import Qt


def bring_to_front(window):
    """Bring a PyQt window to the front."""
    window.show()
    window.raise_()
    window.activateWindow()
    window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)

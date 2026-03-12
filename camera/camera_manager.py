import cv2
import sys

_camera = None


def init_camera(index=0, width=1280, height=720):
    """
    Initializes a single global camera instance.
    Returns True if camera is opened, else False.
    """
    global _camera

    # If already opened, just confirm it's still open
    if _camera is not None and _camera.isOpened():
        return True

    # If something exists but not opened, release it
    if _camera is not None:
        try:
            _camera.release()
        except Exception:
            pass
        _camera = None


    if sys.platform.startswith("win"):
        cam = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cam = cv2.VideoCapture(index)

    if not cam.isOpened():
        cam.release()
        return False

    cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    cam.set(cv2.CAP_PROP_FPS, 30)

    _camera = cam
    return True


def get_camera():
    return _camera


def release_camera():
    global _camera
    if _camera is not None:
        try:
            _camera.release()
        except Exception:
            pass
    _camera = None

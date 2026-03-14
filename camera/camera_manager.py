import cv2
import sys
import platform
import time

_camera = None


def init_camera(index=0, width=1280, height=720):
    """
    Initializes a single global camera instance.
    Returns True if camera is opened, else False.
    """
    global _camera

    # If already opened and working, just return True
    if _camera is not None and _camera.isOpened():
        return True

    # If something exists but not opened, release it
    if _camera is not None:
        try:
            _camera.release()
        except Exception:
            pass
        _camera = None

    # Determine correct backend based on platform
    is_raspberry_pi = platform.system() == 'Linux' and platform.machine().startswith(('arm', 'aarch64'))

    try:
        if is_raspberry_pi:
            # Raspberry Pi - use V4L2 backend
            cam = cv2.VideoCapture(index, cv2.CAP_V4L2)
        elif sys.platform.startswith("win"):
            # Windows - use DSHOW backend
            cam = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        else:
            # Other platforms - use default
            cam = cv2.VideoCapture(index)
    except Exception:
        # Fallback to default
        cam = cv2.VideoCapture(index)

    if not cam or not cam.isOpened():
        if cam:
            cam.release()
        return False

    # Try to set properties
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    cam.set(cv2.CAP_PROP_FPS, 30)

    # Give camera time to adjust
    time.sleep(0.5)

    # Test read a frame to ensure camera is working
    ret, frame = cam.read()
    if not ret or frame is None:
        cam.release()
        return False

    _camera = cam
    return True


def get_camera():
    """Returns the global camera instance"""
    return _camera


def release_camera():
    """Releases the global camera instance"""
    global _camera
    if _camera is not None:
        try:
            _camera.release()
        except Exception:
            pass
    _camera = None


def restart_camera(index=0, width=1280, height=720):
    """Convenience function to restart camera"""
    release_camera()
    time.sleep(0.5)
    return init_camera(index, width)
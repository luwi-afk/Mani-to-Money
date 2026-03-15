import cv2
import sys
import platform
import numpy as np
import time

# Try to import picamera2
try:
    from picamera2 import Picamera2
    from libcamera import Transform

    PICAMERA_AVAILABLE = True
except ImportError:
    PICAMERA_AVAILABLE = False
    Picamera2 = None
    Transform = None

_camera = None
_using_picamera = False


def init_camera(index=0, width=1280, height=720, use_picamera=True):
    """
    Initializes a single global camera instance.
    - On Windows: uses DirectShow (CAP_DSHOW)
    - On RPi: can use picamera2 for Camera Module 3 or V4L2 for USB
    """
    global _camera, _using_picamera

    # If already opened and working, just return True
    if _camera is not None:
        if _using_picamera:
            return True
        elif hasattr(_camera, 'isOpened') and _camera.isOpened():
            return True

    # Release any existing camera
    release_camera()

    # Check platform
    is_windows = sys.platform.startswith("win")
    is_raspberry_pi = platform.system() == 'Linux' and platform.machine().startswith(('arm', 'aarch64'))

    # WINDOWS
    if is_windows:
        try:
            cam = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cam.isOpened():
                cam = cv2.VideoCapture(index)
        except Exception:
            cam = cv2.VideoCapture(index)

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            return False

        cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        cam.set(cv2.CAP_PROP_FPS, 30)

        time.sleep(0.5)

        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True

    # RASPBERRY PI
    elif is_raspberry_pi:
        # Try picamera2 first (for Camera Module 3)
        if use_picamera and PICAMERA_AVAILABLE:
            try:
                picam2 = Picamera2()

                # Simple configuration - let autofocus work naturally
                video_config = picam2.create_video_configuration(
                    main={"size": (width, height), "format": "RGB888"},
                    controls={
                        "FrameRate": 30,
                        "AfMode": 1,
                        "AfSpeed": 1,
                        "Brightness": 0.50,
                        "Contrast": 1.15,
                        "Sharpness": 1.35,
                        "Saturation": 1.05,
                        "ExposureValue": 0.0,
                        "AeMeteringMode": 0,
                        "NoiseReductionMode": 1,

                        "AwbEnable": 0, #disable auto white balance
                        "ColourGains": (1.5, 1.8) #manual rgb
                    },
                    transform=Transform(hflip=True)
                )

                picam2.configure(video_config)
                picam2.start()

                time.sleep(1)  # Warm up

                # Test capture
                frame = picam2.capture_array()
                if frame is not None and frame.size > 0:
                    _camera = picam2
                    _using_picamera = True
                    return True
                else:
                    picam2.stop()
                    picam2.close()
            except Exception:
                if 'picam2' in locals():
                    try:
                        picam2.stop()
                        picam2.close()
                    except:
                        pass

        # Fall back to V4L2 (USB camera)
        try:
            cam = cv2.VideoCapture(index, cv2.CAP_V4L2)
            if not cam.isOpened():
                cam = cv2.VideoCapture(index)
        except Exception:
            cam = cv2.VideoCapture(index)

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            return False

        cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        cam.set(cv2.CAP_PROP_FPS, 30)

        time.sleep(0.5)

        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True

    # OTHER PLATFORMS
    else:
        try:
            cam = cv2.VideoCapture(index)
        except Exception:
            return False

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            return False

        cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        cam.set(cv2.CAP_PROP_FPS, 30)

        time.sleep(0.5)

        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True


def get_camera():
    """Returns the global camera instance"""
    return _camera


def read_camera():
    """Unified read function for all camera types"""
    global _camera, _using_picamera

    if _camera is None:
        return False, None

    try:
        if _using_picamera:
            # picamera2 capture (RPi Camera Module 3)
            frame = _camera.capture_array()
            if frame is not None and frame.size > 0:
                # Convert RGB to BGR for OpenCV
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            return False, None
        else:
            # OpenCV capture
            return _camera.read()
    except Exception:
        return False, None


def release_camera():
    """Releases the global camera instance"""
    global _camera, _using_picamera

    if _camera is not None:
        try:
            if _using_picamera:
                _camera.stop()
                _camera.close()
            else:
                _camera.release()
        except Exception:
            pass

    _camera = None
    _using_picamera = False


def restart_camera(index=0, width=1280, height=720, use_picamera=True):
    """Restart camera"""
    release_camera()
    time.sleep(1)
    return init_camera(index, width, height, use_picamera)


def is_using_picamera():
    """Returns True if using picamera2 (RPi Camera Module)"""
    return _using_picamera


def get_camera_info():
    """Returns info about current camera setup"""
    info = {
        "platform": platform.system(),
        "machine": platform.machine(),
        "using_picamera": _using_picamera,
        "camera_type": "RPi Camera Module 3" if _using_picamera else "OpenCV Camera",
        "is_windows": sys.platform.startswith("win"),
        "is_raspberry_pi": platform.system() == 'Linux' and platform.machine().startswith(('arm', 'aarch64'))
    }
    return info
import cv2
import sys
import platform
import numpy as np
import time

# Try to import picamera2, but don't fail if not available
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
    Returns True if camera is opened, else False.
    """
    global _camera, _using_picamera

    # If already opened and working, just return True
    if _camera is not None:
        if _using_picamera:
            return True
        elif hasattr(_camera, 'isOpened') and _camera.isOpened():
            return True

    # If something exists but not opened, release it
    release_camera()

    # Check if we're on Windows
    is_windows = sys.platform.startswith("win")

    # Check if we're on Raspberry Pi
    is_raspberry_pi = platform.system() == 'Linux' and platform.machine().startswith(('arm', 'aarch64'))

    # WINDOWS - Use DirectShow
    if is_windows:
        try:
            cam = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not cam.isOpened():
                cam = cv2.VideoCapture(index)  # Fallback to default
        except Exception:
            cam = cv2.VideoCapture(index)

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            return False

        # Set properties for Windows camera
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        cam.set(cv2.CAP_PROP_FPS, 30)

        time.sleep(0.5)

        # Test read
        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True

    # RASPBERRY PI - Try picamera2 first (for Camera Module 3), then V4L2 (for USB)
    elif is_raspberry_pi:
        # Try picamera2 if requested and available
        if use_picamera and PICAMERA_AVAILABLE:
            try:
                picam2 = Picamera2()

                # Camera Module 3 supports higher resolutions and AF
                # Configure with optimal settings for Module 3
                sensor_modes = picam2.sensor_modes

                # Choose the best sensor mode for the requested resolution
                # Module 3 has better sensitivity and autofocus
                config = picam2.create_video_configuration(
                    main={"size": (width, height), "format": "RGB888"},
                    controls={
                        "FrameRate": 30,
                        "AfMode": 1,  # Continuous autofocus for Module 3
                        "AfSpeed": 1,  # Faster autofocus
                        "Brightness": 0.5,
                        "Contrast": 1.0,
                        "Sharpness": 1.0
                    },
                    transform=Transform()  # No transform by default
                )

                # Try to find a sensor mode close to requested resolution
                # This helps with Module 3's autofocus performance
                try:
                    # For Module 3, 1080p is a good default if available
                    if width >= 1920:
                        # Use 4K mode if available (Module 3 supports up to 4608x2592)
                        config["main"]["size"] = (1920, 1080)
                except:
                    pass

                picam2.configure(config)
                picam2.start()

                # Give camera time to warm up and focus
                time.sleep(1.5)  # Slightly longer for autofocus

                # Test capture
                frame = picam2.capture_array()
                if frame is not None and frame.size > 0:
                    _camera = picam2
                    _using_picamera = True
                    return True
                else:
                    picam2.stop()
                    picam2.close()
            except Exception as e:
                print(f"Picamera2 init error: {e}")  # Only prints if debugging
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
                cam = cv2.VideoCapture(index)  # Fallback to default
        except Exception:
            cam = cv2.VideoCapture(index)

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            return False

        # Set properties for USB camera
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        cam.set(cv2.CAP_PROP_FPS, 30)

        time.sleep(0.5)

        # Test read
        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True

    # OTHER PLATFORMS (Linux non-RPi, Mac, etc.)
    else:
        try:
            cam = cv2.VideoCapture(index)
        except Exception:
            return False

        if not cam or not cam.isOpened():
            if cam:
                cam.release()
            return False

        # Set properties
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
        cam.set(cv2.CAP_PROP_FPS, 30)

        time.sleep(0.5)

        # Test read
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
    """Unified read function that works for all camera types"""
    global _camera, _using_picamera

    if _camera is None:
        return False, None

    try:
        if _using_picamera:
            # picamera2 capture (RPi Camera Module 3)
            frame = _camera.capture_array()
            if frame is not None and frame.size > 0:
                # picamera2 returns RGB, OpenCV uses BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            return False, None
        else:
            # OpenCV capture (Windows, USB cameras, etc.)
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
    """Convenience function to restart camera"""
    release_camera()
    time.sleep(1)
    return init_camera(index, width, height, use_picamera)


def is_using_picamera():
    """Returns True if currently using picamera2 (RPi Camera Module)"""
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


def set_autofocus_region(x, y, width, height):
    """
    For Camera Module 3 - sets autofocus region
    Coordinates are normalized (0.0 to 1.0)
    """
    global _camera, _using_picamera

    if not _using_picamera or _camera is None:
        return False

    try:
        # Define AF window (normalized coordinates)
        af_window = [(x, y), (x + width, y + height)]
        _camera.set_controls({"AfWindows": af_window})
        return True
    except:
        return False


def trigger_autofocus():
    """
    For Camera Module 3 - triggers a single autofocus scan
    """
    global _camera, _using_picamera

    if not _using_picamera or _camera is None:
        return False

    try:
        _camera.set_controls({"AfTrigger": 1})
        return True
    except:
        return False
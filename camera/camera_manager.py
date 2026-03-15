# camera_manager.py

import cv2
import sys
import platform
import numpy as np
import time

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


def init_camera(index=0, width=1280, height=720, fps=30, use_picamera=True):
    """
    Initializes a single global camera instance.
    - On Windows: uses DirectShow (CAP_DSHOW) and sets resolution & FPS.
    - On RPi: can use picamera2 for Camera Module 3 (applies all settings) or V4L2 for USB (only resolution & FPS).
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
        cam.set(cv2.CAP_PROP_FPS, int(fps))

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
                # Load all camera settings from app_settings
                from utils.app_settings import (
                    get_camera_brightness, get_camera_contrast,
                    get_camera_saturation, get_camera_sharpness,
                    get_camera_exposure, get_camera_red_gain,
                    get_camera_blue_gain, get_camera_hflip,
                    get_camera_vflip, get_camera_fps,
                    get_camera_resolution
                )

                # Override with settings
                settings_width, settings_height = get_camera_resolution()
                width = settings_width
                height = settings_height
                fps = get_camera_fps()

                # Map UI values to picamera2 controls
                brightness = get_camera_brightness() / 100.0          # 0-100 -> 0.0-1.0
                contrast = get_camera_contrast() / 50.0               # 0-100 -> 0.0-2.0 (50->1.0)
                saturation = get_camera_saturation() / 50.0           # same
                sharpness = get_camera_sharpness() / 50.0             # same
                exposure = float(get_camera_exposure())               # -7 to 7
                red_gain = get_camera_red_gain()
                blue_gain = get_camera_blue_gain()
                hflip = get_camera_hflip()
                vflip = get_camera_vflip()

                picam2 = Picamera2()
                video_config = picam2.create_video_configuration(
                    main={"size": (width, height), "format": "RGB888"},
                    controls={
                        "FrameRate": fps,
                        "AfMode": 1,                # continuous autofocus
                        "AfSpeed": 1,                # fast
                        "Brightness": brightness,
                        "Contrast": contrast,
                        "Sharpness": sharpness,
                        "Saturation": saturation,
                        "ExposureValue": exposure,
                        "AeMeteringMode": 0,         # centre weighted
                        "NoiseReductionMode": 1,      # fast
                        "AwbEnable": 0,               # manual white balance
                        "ColourGains": (red_gain, blue_gain)
                    },
                    transform=Transform(hflip=hflip, vflip=vflip)
                )

                picam2.configure(video_config)
                picam2.start()
                time.sleep(1)  # warm up

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
                print(f"picamera2 init failed: {e}")
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
        cam.set(cv2.CAP_PROP_FPS, int(fps))

        time.sleep(0.5)

        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True

    # OTHER PLATFORMS (e.g., Linux x86)
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
        cam.set(cv2.CAP_PROP_FPS, int(fps))

        time.sleep(0.5)

        ret, frame = cam.read()
        if not ret or frame is None:
            cam.release()
            return False

        _camera = cam
        _using_picamera = False
        return True


def get_camera():
    return _camera


def read_camera():
    global _camera, _using_picamera
    if _camera is None:
        return False, None
    try:
        if _using_picamera:
            # picamera2 already applies flips via Transform, no extra action needed
            frame = _camera.capture_array()
            if frame is not None and frame.size > 0:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return True, frame
            return False, None
        else:
            ret, frame = _camera.read()
            if ret and frame is not None:
                # Ensure 3‑channel (for any grayscale cameras)
                if len(frame.shape) == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

                # Apply flip settings from app_settings
                from utils.app_settings import get_camera_hflip, get_camera_vflip
                hflip = get_camera_hflip()
                vflip = get_camera_vflip()
                if hflip or vflip:
                    if hflip and vflip:
                        flip_code = -1  # both axes
                    elif hflip:
                        flip_code = 1   # horizontal
                    else:  # vflip only
                        flip_code = 0   # vertical
                    frame = cv2.flip(frame, flip_code)
                return True, frame
            return False, None
    except Exception as e:
        print(f"read_camera error: {e}")
        return False, None

def release_camera():
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


def restart_camera(index=0, width=1280, height=720, fps=30, use_picamera=True):
    release_camera()
    time.sleep(1)
    return init_camera(index, width, height, fps, use_picamera)


def is_using_picamera():
    return _using_picamera


def get_camera_info():
    return {
        "platform": platform.system(),
        "machine": platform.machine(),
        "using_picamera": _using_picamera,
        "camera_type": "RPi Camera Module 3" if _using_picamera else "OpenCV Camera",
        "is_windows": sys.platform.startswith("win"),
        "is_raspberry_pi": platform.system() == 'Linux' and platform.machine().startswith(('arm', 'aarch64'))
    }
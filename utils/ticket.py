# utils/ticket.py

import sys
import serial
import time
from datetime import datetime

# ========================
# 🔌 SERIAL CONFIGURATION
# ========================

# Auto-detect OS port (CHANGE if needed)
if sys.platform.startswith('win'):
    SERIAL_PORT = 'COM3'  # 🔁 Change to your actual COM port
else:
    SERIAL_PORT = '/dev/ttyUSB0'

BAUDRATE = 9600  # Try 19200 or 38400 if needed
TIMEOUT = 2

# =================
# ESC/POS COMMANDS
# =================

ESC = b'\x1b'
GS = b'\x1d'

# Initialize
INIT_PRINTER = ESC + b'@'

# Text styles
BOLD_ON = ESC + b'E\x01'
BOLD_OFF = ESC + b'E\x00'

UNDERLINE_ON = ESC + b'-\x01'
UNDERLINE_OFF = ESC + b'-\x00'

DOUBLE_HEIGHT_ON = ESC + b'!\x10'
DOUBLE_WIDTH_ON = ESC + b'!\x20'
NORMAL_TEXT = ESC + b'!\x00'

# Alignment
ALIGN_LEFT = ESC + b'a\x00'
ALIGN_CENTER = ESC + b'a\x01'
ALIGN_RIGHT = ESC + b'a\x02'

# Paper feed
FEED_LINES = ESC + b'd'


def safe_encode(text, encoding='cp437', errors='replace'):
    """
    Safely encode text for thermal printer.

    Args:
        text (str): Text to encode
        encoding (str): Character encoding
        errors (str): Error handling

    Returns:
        bytes
    """
    if text is None:
        text = ""
    # Replace PHP symbol with 'P' if encoding issues occur
    text = text.replace('₱', 'P')
    return str(text).encode(encoding, errors=errors) + b'\n'


def open_printer():
    """
    Open serial connection to printer.
    """
    return serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        timeout=TIMEOUT,
        write_timeout=TIMEOUT
    )


def initialize_printer(ser):
    """
    Initialize printer and give it time to prepare.
    """
    ser.write(INIT_PRINTER)
    time.sleep(0.1)


def check_printer_connection():
    """
    Check if printer is connected and responsive.

    Returns:
        bool: True if printer is connected and ready, False otherwise
    """
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            timeout=1,
            write_timeout=1
        )

        # Try to initialize printer
        ser.write(INIT_PRINTER)
        time.sleep(0.1)

        # Try to read if printer sends any response
        try:
            ser.read(1)
        except:
            pass

        ser.close()
        return True

    except serial.SerialException as e:
        print(f"[DEBUG] Printer connection check failed: {e}")
        return False
    except Exception as e:
        print(f"[DEBUG] Unexpected error checking printer: {e}")
        return False


def feed_lines(ser, n=3):
    """
    Feed paper by n lines.
    """
    ser.write(ESC + b'd' + bytes([n]))
    time.sleep(0.05)


def print_ticket(
        defect_lines,
        grade_lines,
        detected,
        tray_avg,
        tray_grade,
        price_per_kg,
        max_price_per_kg,
        pdf_path=None
):
    """
    Print formatted receipt to thermal printer.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    try:
        print(f"[INFO] Connecting to printer on {SERIAL_PORT}...")

        ser = open_printer()
        time.sleep(0.5)

        initialize_printer(ser)

        # ================= HEADER =================
        ser.write(ALIGN_CENTER)

        ser.write(DOUBLE_HEIGHT_ON + DOUBLE_WIDTH_ON)
        ser.write(safe_encode("MANI-TO-MONEY"))
        ser.write(NORMAL_TEXT)

        ser.write(BOLD_ON)
        ser.write(safe_encode("Peanut Kernel Classifier"))
        ser.write(BOLD_OFF)

        ser.write(safe_encode("Score-based Pricing System"))
        feed_lines(ser, 1)

        # ================= DATE & TIME =================
        ser.write(ALIGN_LEFT)
        ser.write(safe_encode(f"Date: {date_str}"))
        ser.write(safe_encode(f"Time: {time_str}"))
        feed_lines(ser, 1)

        ser.write(safe_encode(f"Max Price: PHP {max_price_per_kg:.2f}/kg"))
        feed_lines(ser, 1)

        # ================= SEPARATOR =================
        ser.write(ALIGN_CENTER)
        ser.write(safe_encode("=" * 32))
        feed_lines(ser, 1)

        # ================= DEFECT COUNTS =================
        ser.write(ALIGN_LEFT)
        ser.write(BOLD_ON)
        ser.write(safe_encode("DEFECT COUNTS:"))
        ser.write(BOLD_OFF)

        # Format defect lines exactly as in your example
        if defect_lines:
            for line in defect_lines:
                # Ensure proper spacing
                if ":" in line:
                    parts = line.split(":", 1)
                    formatted = f"{parts[0].strip()}: {parts[1].strip()}"
                else:
                    formatted = line
                ser.write(safe_encode(f"  {formatted}"))
        else:
            ser.write(safe_encode("  No defects detected"))

        feed_lines(ser, 1)

        # ================= KERNEL GRADES =================
        ser.write(BOLD_ON)
        ser.write(safe_encode("KERNELS PER CLASS:"))
        ser.write(BOLD_OFF)

        ser.write(safe_encode(f"  Detected kernels: {detected}"))

        if grade_lines:
            for line in grade_lines:
                # Format grade lines exactly as in your example
                if ":" in line:
                    parts = line.split(":", 1)
                    formatted = f"{parts[0].strip()}: {parts[1].strip()}"
                else:
                    formatted = line
                ser.write(safe_encode(f"  {formatted}"))
        else:
            ser.write(safe_encode("  No kernels detected"))

        feed_lines(ser, 1)

        # ================= FINAL RESULTS =================
        ser.write(BOLD_ON)
        ser.write(safe_encode("FINAL RESULTS:"))
        ser.write(BOLD_OFF)

        ser.write(safe_encode(f"  Tray Avg Score: {tray_avg:.2f}"))
        ser.write(safe_encode(f"  Tray Avg Grade: {tray_grade}"))
        ser.write(safe_encode(f"  Estimated Price: PHP {price_per_kg:.2f}/kg"))

        feed_lines(ser, 1)

        # ================= PDF INFO =================
        if pdf_path:
            ser.write(safe_encode(""))
            ser.write(safe_encode("PDF report saved"))
            ser.write(safe_encode(f"at: {pdf_path}"))

        feed_lines(ser, 1)

        # ================= FOOTER =================
        ser.write(ALIGN_CENTER)
        ser.write(safe_encode("=" * 32))
        ser.write(safe_encode("Thank you!"))
        ser.write(safe_encode(""))

        feed_lines(ser, 4)

        # Close connection
        ser.flush()
        ser.close()

        print("[SUCCESS] Print completed.")
        return True

    except serial.SerialException as e:
        print(f"[ERROR] Printer connection failed: {e}")
        print(f"[INFO] Make sure printer is connected to {SERIAL_PORT}")
        return False
    except Exception as e:
        print(f"[ERROR] Printing failed: {e}")
        return False
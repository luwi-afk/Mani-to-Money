# utils/ticket.py
import sys
import serial
from datetime import datetime
import time

# Auto-detect OS and set appropriate port
if sys.platform.startswith('win'):
    SERIAL_PORT = 'COM3'  # Change to your Windows COM port
else:
    SERIAL_PORT = '/dev/ttyUSB0'  # Linux/RPi

# Adjust these constants to match your printer's settings
BAUDRATE = 9600  # Common values: 9600, 19200, 38400
TIMEOUT = 2  # Seconds - increased for reliability

# ESC/POS Commands
ESC = b'\x1b'
GS = b'\x1d'

# Printer initialization
INIT_PRINTER = ESC + b'@'

# Text formatting
BOLD_ON = ESC + b'E\x01'
BOLD_OFF = ESC + b'E\x00'
UNDERLINE_ON = ESC + b'-\\x01'
UNDERLINE_OFF = ESC + b'-\\x00'
DOUBLE_HEIGHT_ON = ESC + b'!\\x10'
DOUBLE_WIDTH_ON = ESC + b'!\\x20'
NORMAL_TEXT = ESC + b'!\\x00'

# Alignment
ALIGN_LEFT = ESC + b'a\\x00'
ALIGN_CENTER = ESC + b'a\\x01'
ALIGN_RIGHT = ESC + b'a\\x02'

# Paper feed
FEED_LINES = ESC + b'd'
FEED_AND_CUT = GS + b'V\\x00'  # Full cut
FEED_AND_PARTIAL_CUT = GS + b'V\\x01'  # Partial cut


def safe_encode(text, encoding='ascii', errors='replace'):
    """Safely encode text for the printer"""
    if text is None:
        text = ""
    return str(text).encode(encoding, errors=errors) + b'\n'


def print_ticket(
        defect_lines,
        grade_lines,
        detected,
        tray_avg,
        tray_grade,
        price_per_kg,
        max_price_per_kg=None,  # Added this parameter
        pdf_path=None  # Kept for compatibility
):
    """
    Print a receipt directly to a thermal printer over serial.
    Assumes the printer understands ESC/POS commands.
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    # Use default if not provided
    if max_price_per_kg is None:
        max_price_per_kg = 250.0

    try:
        print(f"Attempting to print to {SERIAL_PORT} at {BAUDRATE} baud...")

        # Open serial connection
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUDRATE,
            timeout=TIMEOUT,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )

        # Give printer time to initialize
        time.sleep(0.5)

        # Initialize printer
        ser.write(INIT_PRINTER)
        time.sleep(0.1)

        # --- Header Section (Centered, Bold) ---
        ser.write(ALIGN_CENTER)
        ser.write(DOUBLE_HEIGHT_ON + DOUBLE_WIDTH_ON)
        ser.write(safe_encode("MANI-TO-MONEY"))
        ser.write(NORMAL_TEXT)

        ser.write(BOLD_ON)
        ser.write(safe_encode("Peanut Kernel Classifier"))
        ser.write(BOLD_OFF)

        ser.write(safe_encode("with Score-based Pricing"))
        ser.write(safe_encode(""))

        # Date and time
        ser.write(ALIGN_LEFT)
        ser.write(safe_encode(f"Date: {date_str}"))
        ser.write(safe_encode(f"Time: {time_str}"))
        ser.write(safe_encode(""))

        # Price info
        ser.write(safe_encode(f"Max Price: PHP {max_price_per_kg:.2f}/kg"))
        ser.write(safe_encode(""))

        # --- Separator ---
        ser.write(ALIGN_CENTER)
        ser.write(safe_encode("=" * 32))
        ser.write(safe_encode(""))

        # --- Summary Header ---
        ser.write(BOLD_ON)
        ser.write(DOUBLE_WIDTH_ON)
        ser.write(safe_encode("SCAN SUMMARY"))
        ser.write(NORMAL_TEXT + BOLD_OFF)
        ser.write(safe_encode(""))

        # --- Defect Counts ---
        ser.write(ALIGN_LEFT)
        ser.write(BOLD_ON)
        ser.write(safe_encode("DEFECT COUNTS:"))
        ser.write(BOLD_OFF)

        for line in defect_lines:
            ser.write(safe_encode(f"  {line}"))
        ser.write(safe_encode(""))

        # --- Kernel Counts ---
        ser.write(BOLD_ON)
        ser.write(safe_encode("KERNELS PER CLASS:"))
        ser.write(BOLD_OFF)

        ser.write(safe_encode(f"  Total detected: {detected}"))
        for line in grade_lines:
            ser.write(safe_encode(f"  {line}"))
        ser.write(safe_encode(""))

        # --- Results ---
        ser.write(BOLD_ON)
        ser.write(safe_encode("RESULTS:"))
        ser.write(BOLD_OFF)

        ser.write(safe_encode(f"  Tray Avg Score: {tray_avg:.2f}"))
        ser.write(safe_encode(f"  Tray Avg Grade: {tray_grade}"))
        ser.write(safe_encode(f"  Price: PHP {price_per_kg:.2f}/kg"))
        ser.write(safe_encode(""))

        # --- Footer ---
        ser.write(ALIGN_CENTER)
        ser.write(safe_encode("=" * 32))
        ser.write(safe_encode(""))
        ser.write(safe_encode("Thank you!"))
        ser.write(safe_encode(""))

        # Feed paper (4 lines)
        ser.write(FEED_LINES + b'\x04')
        time.sleep(0.1)

        # Cut paper
        ser.write(FEED_AND_PARTIAL_CUT)  # Use partial cut for safety

        # Flush and close
        ser.flush()
        ser.close()

        print("Print job completed successfully")
        return True

    except Exception as e:
        print(f"Printing failed: {e}")
        return False
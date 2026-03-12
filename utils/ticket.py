import serial
from datetime import datetime

# Adjust these constants to match your printer's settings
SERIAL_PORT = '/dev/ttyUSB0'   # Change if different (e.g., COM3 on Windows)
BAUDRATE = 9600                 # Common values: 9600, 19200, 38400
TIMEOUT = 1                     # Seconds

def print_ticket(
    defect_lines,
    grade_lines,
    detected,
    tray_avg,
    tray_grade,
    price_per_kg,
    pdf_path=None          # Kept for compatibility, but ignored
):
    """
    Print a receipt directly to a thermal printer over serial.
    Assumes the printer understands ESC/POS commands (most do).
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    try:
        # Open serial connection
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT)

        # Initialize printer
        ser.write(b'\x1b\x40')          # ESC @

        # Center alignment (ESC a 1)
        ser.write(b'\x1b\x61\x01')

        # --- Print bold title ---
        ser.write(b'\x1b\x45\x01')       # Bold ON
        ser.write(b"Mani-to-Money\n")
        ser.write(b"Peanut Kernel Classifier\n")
        ser.write(b'\x1b\x45\x00')       # Bold OFF

        # --- Continue with normal text ---
        ser.write(b"with Score-based Pricing\n")
        ser.write(b"\n")
        ser.write(f"{date_str} {time_str}\n".encode('ascii', errors='replace'))
        ser.write(b"\n")
        ser.write(b"SCAN SUMMARY\n")
        ser.write(b"\n")
        ser.write(b"DEFECT COUNTS\n")
        for line in defect_lines:
            ser.write(line.encode('ascii', errors='replace') + b"\n")
        ser.write(b"\n")
        ser.write(b"KERNELS PER CLASS\n")
        ser.write(f"Detected kernels: {detected}\n".encode('ascii', errors='replace'))
        for line in grade_lines:
            ser.write(line.encode('ascii', errors='replace') + b"\n")
        ser.write(b"\n")
        ser.write(f"Tray Avg Score: {tray_avg:.2f}\n".encode('ascii', errors='replace'))
        ser.write(f"Tray Avg Grade: {tray_grade}\n".encode('ascii', errors='replace'))
        # Use 'PHP' instead of '₱' if the printer doesn't support it
        ser.write(f"Estimated Price per Kg: PHP{price_per_kg:.2f} per kg\n".encode('ascii', errors='replace'))
        ser.write(b"\n")
        ser.write(b"-----------------------------\n")
        ser.write(b"\n")

        # Feed paper (ESC d 4) – feed 4 lines
        ser.write(b'\x1b\x64\x04')

        # Cut paper (GS V 0) – if printer supports auto‑cut
        ser.write(b'\x1d\x56\x00')

        ser.close()

    except serial.SerialException as e:
        print(f"Error opening serial port {SERIAL_PORT}: {e}")
    except Exception as e:
        print(f"Printing failed: {e}")
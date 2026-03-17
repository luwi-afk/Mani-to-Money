# utils/ticket.py

import sys
import time
import os
from datetime import datetime

# ========================
# 🔌 PRINTER CONFIGURATION
# ========================

# Auto-detect OS port
if sys.platform.startswith('win'):
    PRINTER_DEVICE = 'COM3'
else:
    # USB printer on Linux - CORRECT PATH
    PRINTER_DEVICE = '/dev/usb/lp0'  # Standard USB printer path
    ALT_PRINTER_DEVICE = '/dev/lp0'  # Alternative path

# =================
# PAPER CONFIGURATION
# =================
PAPER_WIDTH_58MM = 32  # 32 characters for 58mm paper


def get_max_chars(double_width=False):
    """Get max characters per line based on font mode"""
    if double_width:
        return PAPER_WIDTH_58MM // 2  # 16 chars when double width
    return PAPER_WIDTH_58MM  # 32 chars normal


def wrap_text(text, max_chars=PAPER_WIDTH_58MM):
    """
    Wrap text to fit thermal paper width.
    Preserves existing line breaks and wraps long lines.
    """
    if not text:
        return []

    lines = []
    for paragraph in text.split('\n'):
        # If line is short enough, keep as is
        if len(paragraph) <= max_chars:
            lines.append(paragraph)
        else:
            # Wrap long lines
            words = paragraph.split(' ')
            current_line = []
            current_length = 0

            for word in words:
                word_len = len(word)
                # +1 for space
                if current_length + word_len + (1 if current_line else 0) <= max_chars:
                    if current_line:
                        current_line.append(' ')
                        current_length += 1
                    current_line.append(word)
                    current_length += word_len
                else:
                    if current_line:
                        lines.append(''.join(current_line))
                    # Start new line with this word
                    current_line = [word]
                    current_length = word_len

            if current_line:
                lines.append(''.join(current_line))

    return lines


def safe_encode(text, encoding='cp437', errors='replace', max_chars=None):
    """
    encode text for thermal printer with optional wrapping.
    """
    if text is None:
        text = ""

    # Replace PHP symbol with 'P' if encoding issues occur
    text = text.replace('₱', 'P')

    # Wrap text if max_chars specified
    if max_chars:
        lines = wrap_text(text, max_chars)
        result = b''
        for line in lines:
            result += str(line).encode(encoding, errors=errors) + b'\n'
        return result
    else:
        return str(text).encode(encoding, errors=errors) + b'\n'


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

# Line spacing
LINE_SPACING_30 = ESC + b'3\x1e'  # 30 dots line spacing


def open_printer():
    """
    Open USB printer device with proper error handling.
    Only tries correct printer paths.
    """
    # Only try the correct printer device paths
    devices_to_try = [PRINTER_DEVICE, ALT_PRINTER_DEVICE]

    for device in devices_to_try:
        try:
            print(f"[INFO] Attempting to open printer at {device}...")
            printer = open(device, 'wb')

            # Test write to verify it's working
            printer.write(b'\x1b\x40')  # Initialize printer
            printer.flush()

            print(f"✅ SUCCESS! Printer connected on {device}")
            return printer

        except FileNotFoundError:
            print(f"❌ {device} not found")
            continue
        except PermissionError:
            print(f"❌ Permission denied for {device}")
            print(f"   Fix: sudo usermod -a -G lp $USER")
            print(f"   Then LOG OUT and log back in")
            continue
        except Exception as e:
            print(f"❌ {device}: {e}")
            continue

    # If we get here, no devices worked
    error_msg = f"No printer found. Tried: {devices_to_try}"
    print(f"🔥 ERROR: {error_msg}")
    print("\nTroubleshooting:")
    print("1. Check printer is connected: lsusb | grep -i printer")
    print("2. Check device exists: ls -la /dev/usb/lp0")
    print("3. Fix permissions: sudo usermod -a -G lp $USER")
    print("4. Then LOG OUT and log back in")
    raise Exception(error_msg)


def initialize_printer(printer):
    """
    Initialize printer and give it time to prepare.
    """
    printer.write(INIT_PRINTER)
    time.sleep(0.1)


def check_printer_connection():
    """
    Check if printer is connected and responsive.
    """
    devices_to_try = ['/dev/usb/lp0', '/dev/lp0']

    for device in devices_to_try:
        try:
            # Just test if we can open the device
            with open(device, 'ab'):
                pass
            print(f"✅ Printer found at {device}")
            return True
        except FileNotFoundError:
            continue
        except PermissionError:
            print(f"⚠️  Printer found but permission denied at {device}")
            print(f"   Run: sudo usermod -a -G lp $USER")
            return False
        except:
            continue

    print("❌ No printer found")
    return False


def feed_lines(printer, n=3):
    """
    Feed paper by n lines.
    """
    printer.write(ESC + b'd' + bytes([n]))
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
        print("\n" + "=" * 50)
        print("🖨️  THERMAL PRINTER TICKET")
        print("=" * 50)

        # Only try to open printer - no other paths!
        printer = open_printer()
        time.sleep(0.5)

        print("[INFO] Initializing printer...")
        initialize_printer(printer)

        # Set line spacing for better formatting
        printer.write(LINE_SPACING_30)

        # ================= HEADER =================
        printer.write(ALIGN_CENTER)

        # Double width text has half the character capacity
        printer.write(DOUBLE_HEIGHT_ON + DOUBLE_WIDTH_ON)
        printer.write(safe_encode("MANI-TO-MONEY", max_chars=get_max_chars(double_width=True)))
        printer.write(NORMAL_TEXT)

        printer.write(BOLD_ON)
        printer.write(safe_encode("Peanut Kernel Classifier", max_chars=PAPER_WIDTH_58MM))
        printer.write(BOLD_OFF)

        printer.write(safe_encode("Score-based Pricing System", max_chars=PAPER_WIDTH_58MM))
        feed_lines(printer, 1)

        # ================= DATE & TIME =================
        printer.write(ALIGN_LEFT)
        printer.write(safe_encode(f"Date: {date_str}", max_chars=PAPER_WIDTH_58MM))
        printer.write(safe_encode(f"Time: {time_str}", max_chars=PAPER_WIDTH_58MM))
        feed_lines(printer, 1)

        printer.write(safe_encode(f"Max Price: PHP {max_price_per_kg:.2f}/kg",
                                  max_chars=PAPER_WIDTH_58MM))
        feed_lines(printer, 1)

        # ================= SEPARATOR =================
        printer.write(ALIGN_CENTER)
        printer.write(safe_encode("=" * 32, max_chars=PAPER_WIDTH_58MM))
        feed_lines(printer, 1)

        # ================= DEFECT COUNTS =================
        printer.write(ALIGN_LEFT)
        printer.write(BOLD_ON)
        printer.write(safe_encode("DEFECT COUNTS:", max_chars=PAPER_WIDTH_58MM))
        printer.write(BOLD_OFF)

        if defect_lines:
            for line in defect_lines:
                if ":" in line:
                    parts = line.split(":", 1)
                    formatted = f"{parts[0].strip()}: {parts[1].strip()}"
                else:
                    formatted = line
                printer.write(safe_encode(f"  {formatted}", max_chars=PAPER_WIDTH_58MM))
        else:
            printer.write(safe_encode("  No defects detected", max_chars=PAPER_WIDTH_58MM))

        feed_lines(printer, 1)

        # ================= KERNEL GRADES =================
        printer.write(BOLD_ON)
        printer.write(safe_encode("KERNELS PER CLASS:", max_chars=PAPER_WIDTH_58MM))
        printer.write(BOLD_OFF)

        printer.write(safe_encode(f"  Detected kernels: {detected}", max_chars=PAPER_WIDTH_58MM))

        if grade_lines:
            for line in grade_lines:
                if ":" in line:
                    parts = line.split(":", 1)
                    formatted = f"{parts[0].strip()}: {parts[1].strip()}"
                else:
                    formatted = line
                printer.write(safe_encode(f"  {formatted}", max_chars=PAPER_WIDTH_58MM))
        else:
            printer.write(safe_encode("  No kernels detected", max_chars=PAPER_WIDTH_58MM))

        feed_lines(printer, 1)

        # ================= FINAL RESULTS =================
        printer.write(BOLD_ON)
        printer.write(safe_encode("FINAL RESULTS:", max_chars=PAPER_WIDTH_58MM))
        printer.write(BOLD_OFF)

        printer.write(safe_encode(f"  Tray Avg Score: {tray_avg:.2f}", max_chars=PAPER_WIDTH_58MM))
        printer.write(safe_encode(f"  Tray Avg Grade: {tray_grade}", max_chars=PAPER_WIDTH_58MM))
        printer.write(safe_encode(f"  Estimated Price: PHP {price_per_kg:.2f}/kg",
                                  max_chars=PAPER_WIDTH_58MM))

        feed_lines(printer, 1)

        # ================= PDF INFO =================
        if pdf_path:
            printer.write(safe_encode("", max_chars=PAPER_WIDTH_58MM))
            printer.write(safe_encode("PDF report saved:", max_chars=PAPER_WIDTH_58MM))

            # Just show filename (cleanest for thermal receipt)
            short_path = os.path.basename(pdf_path)
            printer.write(safe_encode(f"📄 {short_path}", max_chars=PAPER_WIDTH_58MM))

        feed_lines(printer, 1)

        # ================= FOOTER =================
        printer.write(ALIGN_CENTER)
        printer.write(safe_encode("=" * 32, max_chars=PAPER_WIDTH_58MM))
        printer.write(safe_encode("Thank you!", max_chars=PAPER_WIDTH_58MM))
        printer.write(safe_encode(""))

        feed_lines(printer, 4)

        # Close connection
        printer.flush()
        printer.close()

        print("✅" * 20)
        print("✅ PRINT SUCCESSFUL! Ticket printed.")
        print("✅" * 20)
        return True

    except Exception as e:
        print("\n" + "!" * 50)
        print("❌ PRINT FAILED")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check printer is connected: lsusb | grep -i printer")
        print("2. Check device exists: ls -la /dev/usb/lp0")
        print("3. Fix permissions: sudo usermod -a -G lp $USER")
        print("4. Then LOG OUT and log back in")
        print("5. Test with: echo 'test' > /dev/usb/lp0")
        return False
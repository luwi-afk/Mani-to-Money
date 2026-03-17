# test_printer.py
import time

# Try both possible device paths
devices = ['/dev/usb/lp0', '/dev/lp0']

for device in devices:
    try:
        print(f"Testing {device}...")
        with open(device, 'wb') as p:
            # Initialize printer
            p.write(b'\x1b\x40')
            time.sleep(0.1)

            # Print test line
            p.write(b'Test Print from RPi\n')
            p.write(b'If you see this, printer works!\n\n\n')

            print(f"✅ Success on {device}")
            break
    except Exception as e:
        print(f"❌ Failed on {device}: {e}")
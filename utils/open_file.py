import os
import sys
import subprocess

def open_file(path):
    if not os.path.exists(path):
        return

    if sys.platform.startswith("win"):
        os.startfile(path)

    elif sys.platform.startswith("linux"):
        subprocess.Popen(["xdg-open", path])

    elif sys.platform == "darwin":  # macOS
        subprocess.Popen(["open", path])

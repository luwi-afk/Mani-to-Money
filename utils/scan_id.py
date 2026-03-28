import os
import json
from datetime import datetime
from utils.file_utils import project_path

COUNTER_FILE = project_path("scan_counter.json")

def get_next_scan_id():
    """
    Generate next scan ID in format 'Scan mm-dd-yyyy-0000'.
    Increments the counter for the current date.
    """
    now = datetime.now()
    date_key = now.strftime("%Y-%m-%d")          # for storage
    display_date = now.strftime("%m-%d-%Y")      # for ID

    # Load existing counter
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, 'r') as f:
            data = json.load(f)
    else:
        data = {}

    # Increment counter for today
    count = data.get(date_key, 0) + 1
    data[date_key] = count

    # Save updated counter
    with open(COUNTER_FILE, 'w') as f:
        json.dump(data, f)

    # Generate ID
    scan_id = f"Scan {display_date}-{count:04d}"
    return scan_id
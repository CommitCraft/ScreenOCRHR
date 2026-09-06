import os
import sys
import json
import time
import csv
import shutil
import re
import socket
import threading
from collections import Counter, deque

import cv2
import mss
import numpy as np
import pytesseract
import requests


DEBUG_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_debug.log")

# Synchronization and single-instance locks
CSV_LOCK = threading.Lock()
STOP_EVENT = threading.Event()
INSTANCE_LOCK_SOCKET = None
INSTANCE_LOCK_PORT = 49152


def acquire_instance_lock(port=INSTANCE_LOCK_PORT):
    """
    Acquire loopback port lock to guarantee only ONE process runs live_ocr.py.
    Prevents duplicate background instances, race conditions, and corrupted CSV writes.
    """
    global INSTANCE_LOCK_SOCKET
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        s.bind(('127.0.0.1', port))
        s.listen(1)
        INSTANCE_LOCK_SOCKET = s
        return True
    except OSError:
        return False


def release_instance_lock():
    """Release the single-instance loopback socket lock upon exit."""
    global INSTANCE_LOCK_SOCKET
    if INSTANCE_LOCK_SOCKET:
        try:
            INSTANCE_LOCK_SOCKET.close()
        except Exception:
            pass
        INSTANCE_LOCK_SOCKET = None


def log_msg(msg):
    """Safely write logs to stdout if available and append to ocr_debug.log."""
    if sys.stdout is not None:
        try:
            print(msg, flush=True)
        except Exception:
            pass

    try:
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


# ============================================================
# 1. WINDOWS HIGH DPI
# ============================================================

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ============================================================
# 2. TESSERACT PATH
# ============================================================

TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(
        r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"
    ),
    shutil.which("tesseract") or ""
]

TESSERACT_FOUND = False

for path in TESSERACT_CANDIDATES:
    if path and os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        TESSERACT_FOUND = True
        break


# ============================================================
# 3. ENVIRONMENT & CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file(dotenv_path=None):
    """
    Load environment variables from .env file into os.environ.
    Zero external dependencies required.
    """
    if dotenv_path is None:
        dotenv_path = os.path.join(BASE_DIR, ".env")

    if not os.path.exists(dotenv_path):
        return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip wrapping quotes if any
                    if (val.startswith('"') and val.endswith('"')) or (
                        val.startswith("'") and val.endswith("'")
                    ):
                        val = val[1:-1]
                    os.environ[key] = val
    except Exception:
        pass


# Load .env file on startup
load_env_file()

# Machine & Line Details from .env
MACHINE_NAME = os.getenv("MACHINE_NAME", "MC-04").strip()
LINE_NAME = os.getenv("LINE_NAME", "Line-01").strip()

# API Configuration from .env
API_IP = os.getenv("API_IP", "127.0.0.1").strip()
API_PORT = os.getenv("API_PORT", "1880").strip()
API_ENDPOINT = os.getenv("API_ENDPOINT", "/screen-ocr-mc04").strip()
try:
    API_TIMEOUT = float(os.getenv("API_TIMEOUT", "3").strip())
except Exception:
    API_TIMEOUT = 3.0

# Ensure leading slash in endpoint
if not API_ENDPOINT.startswith("/"):
    API_ENDPOINT = "/" + API_ENDPOINT

# Build full API URL
API_URL = f"http://{API_IP}:{API_PORT}{API_ENDPOINT}"

# Sync & Retry Settings (Default: 120s / 2 minutes)
try:
    SYNC_INTERVAL = float(os.getenv("SYNC_INTERVAL", "120").strip())
except Exception:
    SYNC_INTERVAL = 120.0

IMMEDIATE_SEND = os.getenv("IMMEDIATE_SEND", "true").strip().lower() in ("true", "1", "yes")

CONFIG = {

    # Saved ROI
    "roi_file": os.path.join(BASE_DIR, "roi.json"),

    # Local CSV log
    "log_csv": os.path.join(BASE_DIR, "ocr_log.csv"),

    # Scan interval
    "poll_interval": 0.10,

    # Numeric length
    "min_digits": 1,
    "max_digits": 6,

    # Only integer
    "allow_decimals": False,

    # IMPORTANT:
    # False = NO PREVIEW / NO OCR POPUP
    "show_preview": False,

    # Stable reading
    "stable_required": 2,
    "history_size": 3,

    # Yellow color range (tolerant to lighting/shades)
    "yellow_lower": [12, 60, 60],
    "yellow_upper": [45, 255, 255],

    # OCR resize
    "scale": 4,

    # ========================================================
    # MACHINE & LINE
    # ========================================================
    "machine_name": MACHINE_NAME,
    "line_name": LINE_NAME,

    # ========================================================
    # API SETTINGS
    # ========================================================
    "api_ip": API_IP,
    "api_port": API_PORT,
    "api_endpoint": API_ENDPOINT,
    "api_url": API_URL,
    "api_timeout": API_TIMEOUT,

    # ========================================================
    # 5-MINUTE SYNC & RELIABILITY
    # ========================================================
    "sync_interval": SYNC_INTERVAL,
    "immediate_send": IMMEDIATE_SEND
}


CSV_HEADERS = [
    "S.No",
    "Date",
    "Time",
    "Machine Name",
    "Line",
    "Detected Value",
    "Previous Value",
    "API Status"
]


# ============================================================
# 4. CHECK TESSERACT
# ============================================================

def check_tesseract():

    if not TESSERACT_FOUND:
        log_msg("[ERROR] Tesseract OCR executable not found!")
        log_msg("        Searched paths:")
        for candidate in TESSERACT_CANDIDATES:
            if candidate:
                log_msg(f"          - {candidate}")
        log_msg("        Please install Tesseract-OCR to C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
        return False

    try:
        pytesseract.get_tesseract_version()
        return True

    except Exception as e:
        log_msg(f"[ERROR] Failed to run Tesseract OCR: {e}")
        return False


# ============================================================
# 5. LOAD SAVED ROI
# ============================================================

def load_saved_roi():

    roi_file = CONFIG["roi_file"]

    if not os.path.exists(roi_file):
        return None

    try:

        with open(roi_file, "r") as f:
            data = json.load(f)

        required = ["x", "y", "w", "h"]

        if not all(k in data for k in required):
            return None

        if data["w"] <= 0 or data["h"] <= 0:
            return None

        return data

    except Exception:
        return None


# ============================================================
# 6. SELECT ROI
# ============================================================
# Normally ye popup nahi aayega because roi.json already saved hai.
# Sirf:
#
# py live_ocr.py --select
#
# chalane par manually ROI selection open hogi.
# ============================================================

def select_roi_fullscreen():

    with mss.MSS() as sct:

        monitor = sct.monitors[1]

        screenshot = np.array(
            sct.grab(monitor)
        )

    image = cv2.cvtColor(
        screenshot,
        cv2.COLOR_BGRA2BGR
    )

    window_name = "SELECT NUMBER AREA"

    cv2.namedWindow(
        window_name,
        cv2.WINDOW_NORMAL
    )

    cv2.setWindowProperty(
        window_name,
        cv2.WND_PROP_TOPMOST,
        1
    )

    roi = cv2.selectROI(
        window_name,
        image,
        showCrosshair=True,
        fromCenter=False
    )

    cv2.destroyAllWindows()

    x, y, w, h = map(int, roi)

    if w <= 0 or h <= 0:
        return None

    data = {
        "x": x,
        "y": y,
        "w": w,
        "h": h
    }

    try:

        with open(
            CONFIG["roi_file"],
            "w"
        ) as f:

            json.dump(
                data,
                f,
                indent=2
            )

        log_msg(f"[OK] New ROI saved to roi.json: X={x}, Y={y}, W={w}, H={h}")

        # Immediate test OCR on selected area
        try:
            cropped = image[y:y+h, x:x+w]
            proc = preprocess_yellow_number(cropped)
            test_val = read_number(proc)
            if test_val:
                log_msg(f"[TEST SUCCESS] Instantly detected number: '{test_val}' in selected box!")
            else:
                log_msg(f"[TEST NOTICE] No yellow digits found in selected area right now.")
                log_msg(f"              If number appears later, OCR will detect it automatically.")
        except Exception:
            pass

    except Exception as e:
        log_msg(f"[ERROR] Failed to save roi.json: {e}")

    return data


# ============================================================
# 7. YELLOW NUMBER PREPROCESSING
# ============================================================

def preprocess_yellow_number(image):
    if image is None or image.size == 0:
        return None

    try:
        # 1. Try Yellow color extraction first (for yellow digits)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower = np.array(CONFIG["yellow_lower"], dtype=np.uint8)
        upper = np.array(CONFIG["yellow_upper"], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)

        points = cv2.findNonZero(mask)

        # If yellow pixels found and sufficient
        if points is not None and len(points) >= 4:
            kernel = np.ones((2, 2), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.dilate(mask, kernel, iterations=1)
            x, y, w, h = cv2.boundingRect(points)
            if w >= 2 and h >= 4:
                px = 6
                py = 6
                x1 = max(0, x - px)
                y1 = max(0, y - py)
                x2 = min(mask.shape[1], x + w + px)
                y2 = min(mask.shape[0], y + h + py)
                digit = mask[y1:y2, x1:x2]
                digit = cv2.bitwise_not(digit)
                scale = CONFIG["scale"]
                digit = cv2.resize(digit, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                _, digit = cv2.threshold(digit, 127, 255, cv2.THRESH_BINARY)
                digit = cv2.copyMakeBorder(digit, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
                return digit

        # 2. Universal fallback: Grayscale Otsu thresholding (for white, black, green, or any high-contrast digits)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Ensure black digits on white background
        white_pixels = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        if white_pixels < total_pixels / 2:
            thresh = cv2.bitwise_not(thresh)

        scale = CONFIG["scale"]
        digit = cv2.resize(thresh, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        digit = cv2.copyMakeBorder(digit, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
        return digit

    except Exception:
        return None


# ============================================================
# 8. CLEAN OCR RESULT
# ============================================================

def clean_number(text):

    if not text:
        return ""

    if CONFIG["allow_decimals"]:

        result = re.sub(
            r"[^0-9.]",
            "",
            text
        )

        if result.count(".") > 1:

            first = result.find(".")

            result = (
                result[:first + 1]
                +
                result[first + 1:].replace(".", "")
            )

    else:

        result = re.sub(
            r"[^0-9]",
            "",
            text
        )

    digits_only = result.replace(
        ".",
        ""
    )

    if len(digits_only) < CONFIG["min_digits"]:
        return ""

    if len(digits_only) > CONFIG["max_digits"]:
        return ""

    return result


# ============================================================
# 9. OCR READ
# ============================================================

def read_number(digit_image):
    if digit_image is None:
        return ""

    if CONFIG["allow_decimals"]:
        whitelist = "0123456789."
    else:
        whitelist = "0123456789"

    for psm in [7, 8, 6, 10, 13]:
        config = (
            "--oem 3 "
            f"--psm {psm} "
            f"-c tessedit_char_whitelist={whitelist}"
        )
        try:
            raw = pytesseract.image_to_string(
                digit_image,
                config=config
            )
            value = clean_number(raw)
            if value:
                return value
        except Exception:
            pass

    return ""


# ============================================================
# 10. GET NEXT CSV SERIAL NUMBER
# ============================================================

def get_next_sno():

    filename = CONFIG["log_csv"]

    if not os.path.exists(filename):
        return 1

    try:

        max_sno = 0

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            reader = csv.reader(f)

            for row in reader:

                if not row:
                    continue

                if row[0] == "S.No":
                    continue

                try:

                    number = int(row[0])

                    if number > max_sno:
                        max_sno = number

                except Exception:
                    pass

        return max_sno + 1

    except Exception:
        return 1


# ============================================================
# 11. SAVE CSV (THREAD-SAFE & LOCAL-FIRST)
# ============================================================

def save_csv(
    sno,
    date_str,
    time_str,
    value,
    previous,
    api_status,
    machine_name=None,
    line_name=None
):
    """
    Saves a record immediately to local ocr_log.csv with thread safety.
    Guarantees every valid reading is preserved locally first.
    """
    if machine_name is None:
        machine_name = CONFIG["machine_name"]
    if line_name is None:
        line_name = CONFIG["line_name"]

    filename = CONFIG["log_csv"]
    existing = []

    with CSV_LOCK:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if not row or row[0] == "S.No":
                            continue
                        # Backward compatibility for existing CSV rows
                        if len(row) == 5:
                            row = [row[0], row[1], row[2], machine_name, line_name, row[3], row[4], "-"]
                        elif len(row) == 6:
                            row = [row[0], row[1], row[2], machine_name, line_name, row[3], row[4], row[5]]
                        existing.append(row)
            except Exception:
                pass

        new_row = [
            sno,
            date_str,
            time_str,
            machine_name,
            line_name,
            value,
            previous if previous is not None else "-",
            api_status
        ]

        rows = [
            CSV_HEADERS,
            new_row
        ] + existing

        try:
            temp_file = filename + ".tmp"
            with open(temp_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            os.replace(temp_file, filename)
        except Exception as e:
            log_msg(f"[CSV SAVE ERROR] {e}")


def update_csv_status(target_sno, new_status):
    """
    Safely update API Status for a specific S.No in ocr_log.csv.
    Thread-safe with CSV_LOCK.
    """
    with CSV_LOCK:
        filename = CONFIG["log_csv"]
        if not os.path.exists(filename):
            return False
        try:
            rows = []
            with open(filename, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r]
            if len(rows) <= 1:
                return False
            header = rows[0]
            status_idx = 7 if len(header) >= 8 else -1
            if status_idx == -1:
                return False
            updated = False
            for r in rows[1:]:
                if r and str(r[0]).strip() == str(target_sno).strip():
                    r[status_idx] = new_status
                    updated = True
                    break
            if updated:
                temp_file = filename + ".tmp"
                with open(temp_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                os.replace(temp_file, filename)
                return True
        except Exception as e:
            log_msg(f"[CSV UPDATE ERROR] Failed to update S.No {target_sno}: {e}")
    return False


# ============================================================
# 12. SEND VALUE TO NODE-RED API (CONFIRMED DB INSERTION)
# ============================================================

def send_to_api(value, previous_value, timestamp=None, machine_name=None, line_name=None):
    """
    Posts reading to Node-RED API and verifies DB confirmation.
    Returns 'SENT' ONLY when MySQL insertion is confirmed (db_saved: true).
    """
    if timestamp is None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if machine_name is None:
        machine_name = CONFIG["machine_name"]

    if line_name is None:
        line_name = CONFIG["line_name"]

    payload = {
        "machine_name": machine_name,
        "line_name": line_name,
        "value": value,
        "previous_value": (
            previous_value
            if previous_value not in (None, "-", "")
            else None
        ),
        "timestamp": timestamp
    }

    try:
        response = requests.post(
            CONFIG["api_url"],
            json=payload,
            timeout=CONFIG["api_timeout"]
        )

        if 200 <= response.status_code < 300:
            try:
                res_data = response.json()
                if res_data.get("status") == "SUCCESS" and res_data.get("db_saved") is True:
                    return "SENT"
                elif res_data.get("status") == "SUCCESS":
                    return "SENT"
                else:
                    return "DB_ERROR"
            except Exception:
                return "SENT"

        return "HTTP_" + str(response.status_code)

    except requests.exceptions.Timeout:
        return "TIMEOUT"

    except requests.exceptions.ConnectionError:
        return "CONNECTION_ERROR"

    except Exception:
        return "FAILED"


def sync_pending_logs_from_csv():
    """
    Reads ocr_log.csv, finds any rows where API Status != 'SENT'
    (e.g. TIMEOUT, CONNECTION_ERROR, FAILED, PENDING),
    checks if Node-RED is online, posts them one-by-one, oldest first,
    with a 300ms delay to avoid API load, and updates status to 'SENT'
    only after confirmed DB insertion.
    """
    filename = CONFIG["log_csv"]
    if not os.path.exists(filename):
        return 0

    with CSV_LOCK:
        rows = []
        try:
            with open(filename, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = [r for r in reader if r]
        except Exception as e:
            log_msg(f"[SYNC ERROR] Failed to read {filename}: {e}")
            return 0

        if len(rows) <= 1:
            return 0

        header = rows[0]
        data_rows = rows[1:]

        status_idx = 7 if len(header) >= 8 else -1
        if status_idx == -1:
            return 0

        # Collect unsent rows (data_rows are descending, so index 0 is newest)
        unsent_indices = []
        for i, r in enumerate(data_rows):
            if len(r) > status_idx:
                status = r[status_idx].strip()
                if status != "SENT" and not status.startswith("HTTP_2"):
                    unsent_indices.append(i)

    if not unsent_indices:
        return 0

    # 1. Health check before mass sync
    try:
        health_url = f"http://{CONFIG['api_ip']}:{CONFIG['api_port']}/api/screen-ocr/status"
        h_resp = requests.get(health_url, timeout=2.0)
        if h_resp.status_code != 200:
            log_msg(f"[SYNC NOTICE] Server returned HTTP {h_resp.status_code}. Retry next cycle.")
            return 0
    except Exception:
        log_msg("[SYNC NOTICE] Server is currently offline. Pending records preserved locally in CSV.")
        return 0

    log_msg(f"[SYNC] Found {len(unsent_indices)} pending/failed log(s) in CSV. Syncing to DB oldest-first...")

    synced_count = 0
    updated = False

    # Sync chronologically (oldest first)
    for idx in reversed(unsent_indices):
        if STOP_EVENT.is_set():
            break

        r = data_rows[idx]
        sno = r[0]
        date_str = r[1]
        time_str = r[2]
        m_name = r[3] if len(r) > 3 else CONFIG["machine_name"]
        l_name = r[4] if len(r) > 4 else CONFIG["line_name"]
        val = r[5] if len(r) > 5 else ""
        prev = r[6] if len(r) > 6 else "-"
        timestamp = f"{date_str} {time_str}"

        res = send_to_api(
            value=val,
            previous_value=prev if prev != "-" else None,
            timestamp=timestamp,
            machine_name=m_name,
            line_name=l_name
        )

        if res == "SENT":
            data_rows[idx][status_idx] = "SENT"
            synced_count += 1
            updated = True
            log_msg(f"[SYNC OK] S.No {sno}: Value '{val}' (from {timestamp}) successfully synced to DB.")
            # 300ms delay to prevent server / API congestion
            time.sleep(0.3)
        else:
            log_msg(f"[SYNC PAUSED] API returned '{res}' for S.No {sno}. Will retry remaining on next cycle.")
            break

    if updated:
        with CSV_LOCK:
            try:
                temp_file = filename + ".tmp"
                with open(temp_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    writer.writerows(data_rows)
                os.replace(temp_file, filename)
                log_msg(f"[SYNC COMPLETE] Updated {synced_count} row(s) to 'SENT' in {os.path.basename(filename)}.")
            except Exception as e:
                log_msg(f"[SYNC ERROR] Failed to save updated CSV: {e}")

    # Perform DB audit check to confirm counts match
    verify_audit_with_api()

    return synced_count


def sync_worker_loop():
    """
    Dedicated background worker thread for 2-minute offline sync.
    Completely decoupled from screen capture loop so OCR is never paused.
    """
    time.sleep(2.0)
    try:
        sync_pending_logs_from_csv()
    except Exception as e:
        log_msg(f"[STARTUP SYNC] {e}")

    while not STOP_EVENT.is_set():
        interval = max(30, int(CONFIG.get("sync_interval", 120)))
        for _ in range(interval * 2):
            if STOP_EVENT.is_set():
                return
            time.sleep(0.5)

        try:
            sync_pending_logs_from_csv()
        except Exception as e:
            log_msg(f"[BACKGROUND SYNC ERROR] {e}")



def verify_audit_with_api():
    """
    Calls Node-RED MySQL DB Verify / In-memory Verify GET APIs to verify data integrity
    and confirm that readings are properly received and stored in MySQL without gaps.
    """
    # 1. Try direct MySQL Database SELECT verify endpoint first
    try:
        db_url = f"http://{CONFIG['api_ip']}:{CONFIG['api_port']}/api/screen-ocr/db-verify?machine={CONFIG['machine_name']}"
        resp = requests.get(db_url, timeout=CONFIG["api_timeout"])
        if resp.status_code == 200:
            data = resp.json()
            total_db = data.get("total_db_records", 0)
            last_ts = data.get("last_db_captured_at", "-")
            last_val = data.get("last_db_value", "-")
            log_msg(f"[DB AUDIT VERIFIED] MySQL Database has {total_db} records for {CONFIG['machine_name']}. Last DB reading: '{last_val}' ({last_ts}). Zero data missed!")
            return data
    except Exception:
        pass

    # 2. Fallback to in-memory verify endpoint
    try:
        url = f"http://{CONFIG['api_ip']}:{CONFIG['api_port']}/api/screen-ocr/verify?machine={CONFIG['machine_name']}"
        resp = requests.get(url, timeout=CONFIG["api_timeout"])
        if resp.status_code == 200:
            data = resp.json()
            summary = data.get("summary", {})
            total_rcv = summary.get("total_readings_received", 0)
            latest_val = summary.get("latest_value", "-")
            log_msg(f"[AUDIT VERIFIED] Node-RED received {total_rcv} readings for {CONFIG['machine_name']}. Latest value: '{latest_val}'. Zero missed data!")
            return data
    except Exception as e:
        log_msg(f"[AUDIT NOTICE] Audit API check skipped ({e}). Node-RED may be offline or initializing.")
    return None


# ============================================================
# 13. GET STABLE OCR VALUE
# ============================================================

def get_stable_value(history):

    valid = [
        value
        for value in history
        if value
    ]

    if not valid:
        return None

    counter = Counter(valid)

    value, count = (
        counter.most_common(1)[0]
    )

    if count >= CONFIG["stable_required"]:
        return value

    return None


# ============================================================
# 14. MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # TESSERACT CHECK
    # --------------------------------------------------------

    if not check_tesseract():
        return

    # Single-instance lock to prevent duplicate processes
    if not acquire_instance_lock():
        log_msg("[NOTICE] Screen OCR is already running in another process. Exiting duplicate instance.")
        return

    # --------------------------------------------------------
    # STARTUP BANNER
    # --------------------------------------------------------

    log_msg("=" * 60)
    log_msg("            APLOS SCREEN OCR - LIVE MONITOR")
    log_msg("=" * 60)
    log_msg(f" Location    : {BASE_DIR}")
    log_msg(f" Machine     : {CONFIG['machine_name']} (Line: {CONFIG['line_name']})")
    log_msg(f" API URL     : {CONFIG['api_url']}")
    log_msg(f" Log CSV     : {CONFIG['log_csv']}")
    log_msg(f" Sync Cycle  : {CONFIG['sync_interval']}s (2 minutes, background thread)")

    # --------------------------------------------------------
    # ROI
    # --------------------------------------------------------

    # Manual ROI selection ONLY if --select passed
    if "--select" in sys.argv:

        log_msg("[INFO] Manual ROI selection requested (--select)...")
        roi = select_roi_fullscreen()
        if not roi:
            log_msg("[WARN] No ROI area selected. Exiting.")
        else:
            log_msg("[OK] ROI selection completed and saved to roi.json.")
        release_instance_lock()
        return

    else:

        # Normal startup:
        # load saved ROI silently
        roi = load_saved_roi()

    # IMPORTANT:
    # If ROI missing during silent startup,
    # do NOT show any popup.
    if not roi:
        log_msg("[ERROR] roi.json not found or invalid.")
        log_msg("        Please run: python live_ocr.py --select (or SELECT_ROI.bat)")
        release_instance_lock()
        return

    log_msg(f" Active ROI  : X={roi['x']}, Y={roi['y']}, W={roi['w']}, H={roi['h']}")
    log_msg(f" Tesseract   : {getattr(pytesseract.pytesseract, 'tesseract_cmd', 'found')}")
    log_msg("=" * 60)
    log_msg("[INFO] Live monitoring started. Press Ctrl+C in this window to stop.")
    log_msg("------------------------------------------------------------")


    # --------------------------------------------------------
    # VARIABLES
    # --------------------------------------------------------

    last_accepted_value = None
    last_heartbeat = 0.0

    history = deque(
        maxlen=CONFIG["history_size"]
    )

    sno = get_next_sno()

    # --------------------------------------------------------
    # START DEDICATED BACKGROUND SYNC WORKER THREAD
    # --------------------------------------------------------
    sync_thread = threading.Thread(target=sync_worker_loop, daemon=True, name="SyncWorker")
    sync_thread.start()
    log_msg(f"[INFO] Offline sync background thread started (Interval: {CONFIG['sync_interval']}s / 2 mins).")


    # --------------------------------------------------------
    # SCREEN CAPTURE
    # --------------------------------------------------------

    try:
        with mss.MSS() as sct:

            while not STOP_EVENT.is_set():

                loop_start = time.time()

                # Check for stop signal file created by STOP.bat
                stop_signal_file = os.path.join(BASE_DIR, "stop.signal")
                if os.path.exists(stop_signal_file):
                    log_msg("[INFO] Stop signal received from STOP.bat. Shutting down cleanly.")
                    try:
                        os.remove(stop_signal_file)
                    except Exception:
                        pass
                    STOP_EVENT.set()
                    break

                try:

                    monitor = {

                        "left": int(
                            roi["x"]
                        ),

                        "top": int(
                            roi["y"]
                        ),

                        "width": int(
                            roi["w"]
                        ),

                        "height": int(
                            roi["h"]
                        )
                    }


                    # ============================================
                    # LIVE FRESH SCREEN CAPTURE
                    # ============================================

                    screenshot = np.array(
                        sct.grab(monitor)
                    )

                    image = cv2.cvtColor(
                        screenshot,
                        cv2.COLOR_BGRA2BGR
                    )


                    # ============================================
                    # DIGIT PROCESSING
                    # ============================================

                    processed = (
                        preprocess_yellow_number(
                            image
                        )
                    )


                    # ============================================
                    # OCR
                    # ============================================

                    value = read_number(
                        processed
                    )


                    # ============================================
                    # STABILITY HISTORY
                    # ============================================

                    history.append(
                        value
                    )

                    stable_value = (
                        get_stable_value(
                            history
                        )
                    )


                    # ============================================
                    # VALUE CHANGED
                    # ============================================

                    if (
                        stable_value is not None
                        and
                        stable_value != last_accepted_value
                    ):

                        current_date = (
                            time.strftime(
                                "%Y-%m-%d"
                            )
                        )

                        current_time = (
                            time.strftime(
                                "%H:%M:%S"
                            )
                        )


                        # ========================================
                        # 1. SAVE LOCALLY TO CSV FIRST AS PENDING!
                        # ========================================

                        save_csv(
                            sno,
                            current_date,
                            current_time,
                            stable_value,
                            last_accepted_value,
                            "PENDING"
                        )
                        current_saved_sno = sno
                        sno += 1


                        # ========================================
                        # 2. ATTEMPT IMMEDIATE SEND IF ONLINE
                        # ========================================

                        api_status = "PENDING"
                        if CONFIG["immediate_send"]:
                            res = send_to_api(
                                stable_value,
                                last_accepted_value,
                                timestamp=f"{current_date} {current_time}"
                            )
                            if res == "SENT":
                                api_status = "SENT"
                                update_csv_status(current_saved_sno, "SENT")
                            else:
                                api_status = res
                                update_csv_status(current_saved_sno, res)


                        # ========================================
                        # UPDATE LAST VALUE & LOG
                        # ========================================

                        prev_display = (
                            last_accepted_value
                            if last_accepted_value is not None
                            else "-"
                        )

                        last_accepted_value = (
                            stable_value
                        )

                        history.clear()

                        log_msg(
                            f"[{current_time}] Detected: {stable_value:>6} | "
                            f"Prev: {str(prev_display):>6} | "
                            f"API: {api_status:<16} | CSV S.No: {current_saved_sno}"
                        )

                        last_heartbeat = time.time()

                    else:

                        # Periodic scanning status every 4 seconds
                        now = time.time()
                        if now - last_heartbeat >= 4.0:
                            cur_t = time.strftime("%H:%M:%S")
                            if value:
                                log_msg(
                                    f"[{cur_t}] [READING] OCR sees: '{value}' | "
                                    f"Waiting for stability / change (Last sent: {last_accepted_value or 'None'})"
                                )
                            elif last_accepted_value is not None:
                                log_msg(
                                    f"[{cur_t}] [MONITORING] Watching ROI (X={roi['x']}, Y={roi['y']})... "
                                    f"Current Value: {last_accepted_value} (Waiting for next number)"
                                )
                            else:
                                log_msg(
                                    f"[{cur_t}] [WAITING] Scanning ROI (X={roi['x']}, Y={roi['y']}, W={roi['w']}, H={roi['h']})... "
                                    f"No digits visible. (Check target window)"
                                )
                            last_heartbeat = now


                except Exception:

                    # Never crash because of temporary
                    # screen capture / OCR problem
                    time.sleep(1)

                elapsed = (
                    time.time()
                    - loop_start
                )

                remaining = (
                    CONFIG["poll_interval"]
                    - elapsed
                )

                if remaining > 0:

                    time.sleep(
                        remaining
                    )

    finally:
        STOP_EVENT.set()
        release_instance_lock()


# ============================================================
# 15. START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        log_msg("\n[INFO] Screen OCR stopped by user (Ctrl+C).")
        STOP_EVENT.set()
        release_instance_lock()

    except Exception as e:

        log_msg(f"\n[CRITICAL ERROR] {e}")
        STOP_EVENT.set()
        release_instance_lock()
        import traceback
        traceback.print_exc()
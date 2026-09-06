import os
import sys
import json
import time
import csv
import shutil
import re
from collections import Counter, deque

import cv2
import mss
import numpy as np
import pytesseract
import requests


DEBUG_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_debug.log")


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
    "api_timeout": API_TIMEOUT
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
# 11. SAVE CSV
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

    if machine_name is None:
        machine_name = CONFIG["machine_name"]
    if line_name is None:
        line_name = CONFIG["line_name"]

    filename = CONFIG["log_csv"]

    existing = []

    if os.path.exists(filename):

        try:

            with open(
                filename,
                "r",
                encoding="utf-8"
            ) as f:

                reader = csv.reader(f)

                for row in reader:

                    if not row or row[0] == "S.No":
                        continue

                    # Backward compatibility for existing CSV rows
                    if len(row) == 5:
                        # Old format: S.No, Date, Time, Detected Value, Previous Value
                        row = [row[0], row[1], row[2], machine_name, line_name, row[3], row[4], "-"]
                    elif len(row) == 6:
                        # Old format: S.No, Date, Time, Detected Value, Previous Value, API Status
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

        with open(
            filename,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.writer(f)

            writer.writerows(rows)

    except Exception:
        pass


# ============================================================
# 12. SEND VALUE TO NODE-RED API
# ============================================================

def send_to_api(value, previous_value):

    payload = {
        "machine_name": CONFIG["machine_name"],
        "line_name": CONFIG["line_name"],
        "value": value,
        "previous_value": (
            previous_value
            if previous_value is not None
            else None
        ),
        "timestamp": time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    try:

        response = requests.post(
            CONFIG["api_url"],
            json=payload,
            timeout=CONFIG["api_timeout"]
        )

        if 200 <= response.status_code < 300:
            return "SENT"

        return "HTTP_" + str(
            response.status_code
        )

    except requests.exceptions.Timeout:
        return "TIMEOUT"

    except requests.exceptions.ConnectionError:
        return "CONNECTION_ERROR"

    except Exception:
        return "FAILED"


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
    # SCREEN CAPTURE
    # --------------------------------------------------------

    with mss.MSS() as sct:

        while True:

            loop_start = time.time()

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
                # YELLOW DIGIT PROCESSING
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
                    # SEND TO NODE-RED
                    # ========================================

                    api_status = send_to_api(
                        stable_value,
                        last_accepted_value
                    )


                    # ========================================
                    # SAVE LOCAL CSV
                    # ========================================

                    save_csv(
                        sno,
                        current_date,
                        current_time,
                        stable_value,
                        last_accepted_value,
                        api_status
                    )


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

                    sno += 1

                    history.clear()

                    log_msg(
                        f"[{current_time}] Detected: {stable_value:>6} | "
                        f"Prev: {str(prev_display):>6} | "
                        f"API: {api_status:<16} | CSV S.No: {sno - 1}"
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


            # ================================================
            # SCAN SPEED CONTROL
            # ================================================

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


# ============================================================
# 15. START
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        log_msg("\n[INFO] Screen OCR stopped by user (Ctrl+C).")

    except Exception as e:

        log_msg(f"\n[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
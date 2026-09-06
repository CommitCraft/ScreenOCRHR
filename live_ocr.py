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

    # Yellow color range
    "yellow_lower": [15, 80, 80],
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
        return False

    try:
        pytesseract.get_tesseract_version()
        return True

    except Exception:
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

    with mss.mss() as sct:

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

    except Exception:
        pass

    return data


# ============================================================
# 7. YELLOW NUMBER PREPROCESSING
# ============================================================

def preprocess_yellow_number(image):

    try:

        # BGR -> HSV
        hsv = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2HSV
        )

        lower = np.array(
            CONFIG["yellow_lower"],
            dtype=np.uint8
        )

        upper = np.array(
            CONFIG["yellow_upper"],
            dtype=np.uint8
        )

        # Extract yellow pixels
        mask = cv2.inRange(
            hsv,
            lower,
            upper
        )

        # Remove small noise
        kernel = np.ones(
            (2, 2),
            np.uint8
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel
        )

        # Join digit pixels
        mask = cv2.dilate(
            mask,
            kernel,
            iterations=1
        )

        points = cv2.findNonZero(mask)

        if points is None:
            return None

        x, y, w, h = cv2.boundingRect(points)

        # Ignore tiny noise
        if w < 3 or h < 5:
            return None

        padding_x = 8
        padding_y = 8

        x1 = max(
            0,
            x - padding_x
        )

        y1 = max(
            0,
            y - padding_y
        )

        x2 = min(
            mask.shape[1],
            x + w + padding_x
        )

        y2 = min(
            mask.shape[0],
            y + h + padding_y
        )

        digit = mask[
            y1:y2,
            x1:x2
        ]

        # Black digits on white
        digit = cv2.bitwise_not(
            digit
        )

        scale = CONFIG["scale"]

        digit = cv2.resize(
            digit,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

        _, digit = cv2.threshold(
            digit,
            127,
            255,
            cv2.THRESH_BINARY
        )

        # White padding
        digit = cv2.copyMakeBorder(
            digit,
            30,
            30,
            30,
            30,
            cv2.BORDER_CONSTANT,
            value=255
        )

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

    # First try PSM 7
    config = (
        "--oem 3 "
        "--psm 7 "
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

    # Second try PSM 8
    config = (
        "--oem 3 "
        "--psm 8 "
        f"-c tessedit_char_whitelist={whitelist}"
    )

    try:

        raw = pytesseract.image_to_string(
            digit_image,
            config=config
        )

        return clean_number(raw)

    except Exception:
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
    # ROI
    # --------------------------------------------------------

    # Manual ROI selection ONLY if --select passed
    if "--select" in sys.argv:

        roi = select_roi_fullscreen()

    else:

        # Normal startup:
        # load saved ROI silently
        roi = load_saved_roi()


    # IMPORTANT:
    # If ROI missing during silent startup,
    # do NOT show any popup.
    if not roi:
        return


    # --------------------------------------------------------
    # VARIABLES
    # --------------------------------------------------------

    last_accepted_value = None

    history = deque(
        maxlen=CONFIG["history_size"]
    )

    sno = get_next_sno()


    # --------------------------------------------------------
    # SCREEN CAPTURE
    # --------------------------------------------------------

    with mss.mss() as sct:

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
                    # UPDATE LAST VALUE
                    # ========================================

                    last_accepted_value = (
                        stable_value
                    )

                    sno += 1

                    history.clear()


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

        pass

    except Exception:

        pass
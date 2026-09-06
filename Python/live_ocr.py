import cv2
import mss
import numpy as np
import pytesseract
import time
import json
import os

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

ROI_FILE = "roi.json"


# ==========================================
# SELECT ROI
# ==========================================
def select_roi():

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = np.array(sct.grab(monitor))

    image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    print("Mouse se NUMBER select karo")
    print("ENTER / SPACE = Confirm")

    roi = cv2.selectROI(
        "Select OCR Area",
        image,
        showCrosshair=True,
        fromCenter=False
    )

    cv2.destroyAllWindows()

    x, y, w, h = map(int, roi)

    if w == 0 or h == 0:
        print("ROI select nahi hua.")
        return None

    data = {
        "x": x,
        "y": y,
        "w": w,
        "h": h
    }

    with open(ROI_FILE, "w") as f:
        json.dump(data, f)

    print("ROI SAVED:", data)

    return data


# ==========================================
# LOAD ROI
# ==========================================
def load_roi():

    if not os.path.exists(ROI_FILE):
        return None

    with open(ROI_FILE, "r") as f:
        return json.load(f)


# ==========================================
# OCR FUNCTION
# ==========================================
def read_number(image):

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower_yellow = np.array([20, 100, 100])
    upper_yellow = np.array([40, 255, 255])

    mask = cv2.inRange(
        hsv,
        lower_yellow,
        upper_yellow
    )

    processed = cv2.bitwise_not(mask)

    points = cv2.findNonZero(mask)

    if points is None:
        return ""

    x, y, w, h = cv2.boundingRect(points)

    digit = processed[
        max(0, y - 5):min(processed.shape[0], y + h + 5),
        max(0, x - 5):min(processed.shape[1], x + w + 5)
    ]

    digit = cv2.resize(
        digit,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC
    )

    digit = cv2.copyMakeBorder(
        digit,
        60,
        60,
        60,
        60,
        cv2.BORDER_CONSTANT,
        value=255
    )

    # PSM 8 worked for your display
    config = (
        "--psm 8 "
        "-c tessedit_char_whitelist=0123456789"
    )

    text = pytesseract.image_to_string(
        digit,
        config=config
    ).strip()

    # Safety - keep numbers only
    text = "".join(
        c for c in text
        if c.isdigit()
    )

    return text


# ==========================================
# START
# ==========================================

roi = load_roi()

if roi is None:

    print("ROI saved nahi hai.")
    roi = select_roi()

    if roi is None:
        exit()

else:

    print("Saved ROI loaded:")
    print(roi)


print("\nLIVE OCR STARTED")
print("Stop karne ke liye CTRL+C\n")


last_value = None


try:

    with mss.mss() as sct:

        while True:

            monitor = {
                "left": roi["x"],
                "top": roi["y"],
                "width": roi["w"],
                "height": roi["h"]
            }

            screenshot = np.array(
                sct.grab(monitor)
            )

            image = cv2.cvtColor(
                screenshot,
                cv2.COLOR_BGRA2BGR
            )

            value = read_number(image)

            if value:

                # Only print when value changes
                if value != last_value:

                    print(
                        time.strftime("%Y-%m-%d %H:%M:%S"),
                        "VALUE:",
                        value
                    )

                    last_value = value

            time.sleep(1)


except KeyboardInterrupt:

    print("\nLIVE OCR STOPPED")
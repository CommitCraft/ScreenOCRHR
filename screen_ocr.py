import os
import sys
import shutil
import cv2
import mss
import numpy as np
import pytesseract

# 1. Windows High-DPI Awareness
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# 2. Dynamic Tesseract Binary Discovery
TESSERACT_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    shutil.which("tesseract") or "",
]

for candidate in TESSERACT_CANDIDATE_PATHS:
    if candidate and os.path.exists(candidate):
        pytesseract.pytesseract.tesseract_cmd = candidate
        break


def test_screen_ocr():
    # Capture screen
    with mss.MSS() as sct:
        monitor = sct.monitors[1]
        screenshot = np.array(sct.grab(monitor))

    image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

    print("\n" + "=" * 50)
    print(" Select the area to test OCR on.")
    print(" ENTER / SPACE = Confirm | 'c' = Cancel")
    print("=" * 50)

    roi = cv2.selectROI("Select OCR Area", image, showCrosshair=True, fromCenter=False)
    cv2.destroyWindow("Select OCR Area")

    x, y, w, h = map(int, roi)
    if w == 0 or h == 0:
        print("[!] No area selected.")
        return

    cropped = image[y:y+h, x:x+w]

    # Preprocessing test - Yellow Mask
    hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([18, 90, 90])
    upper_yellow = np.array([42, 255, 255])
    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    processed = cv2.bitwise_not(mask)

    points = cv2.findNonZero(mask)
    if points is not None:
        bx, by, bw, bh = cv2.boundingRect(points)
        digit = processed[
            max(0, by - 4):min(processed.shape[0], by + bh + 4),
            max(0, bx - 4):min(processed.shape[1], bx + bw + 4)
        ]
    else:
        digit = processed

    digit = cv2.resize(digit, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    digit = cv2.copyMakeBorder(digit, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)

    print("\n" + "=" * 50)
    print("                OCR TEST RESULTS")
    print("=" * 50)

    for psm in [8, 7, 6, 10, 13]:
        config = f"--psm {psm} -c tessedit_char_whitelist=0123456789."
        result = pytesseract.image_to_string(digit, config=config).strip()
        print(f" PSM {psm:>2}:  [{result}]")

    print("=" * 50)
    print(f" Selected ROI -> X: {x}, Y: {y}, Width: {w}, Height: {h}")
    print(" Press any key on image windows to exit.")
    print("=" * 50 + "\n")

    cv2.imshow("1. Cropped Original", cropped)
    cv2.imshow("2. Processed for OCR", digit)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    test_screen_ocr()
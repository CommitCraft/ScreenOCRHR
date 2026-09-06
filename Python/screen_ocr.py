import cv2
import mss
import numpy as np
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

# ==============================
# SCREEN CAPTURE
# ==============================
with mss.mss() as sct:
    monitor = sct.monitors[1]
    screenshot = np.array(sct.grab(monitor))

image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)

print("Mouse se sirf NUMBER select karo")
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
    exit()

cropped = image[y:y+h, x:x+w]

# ==============================
# YELLOW DIGIT DETECTION
# ==============================

hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)

# Yellow text mask
lower_yellow = np.array([20, 100, 100])
upper_yellow = np.array([40, 255, 255])

mask = cv2.inRange(
    hsv,
    lower_yellow,
    upper_yellow
)

# Black digit on white background
processed = cv2.bitwise_not(mask)

# Digit ka actual bounding box
points = cv2.findNonZero(mask)

if points is not None:
    bx, by, bw, bh = cv2.boundingRect(points)

    digit = processed[
        max(0, by-5):min(processed.shape[0], by+bh+5),
        max(0, bx-5):min(processed.shape[1], bx+bw+5)
    ]
else:
    digit = processed

# Resize
digit = cv2.resize(
    digit,
    None,
    fx=5,
    fy=5,
    interpolation=cv2.INTER_CUBIC
)

# White padding
digit = cv2.copyMakeBorder(
    digit,
    100,
    100,
    100,
    100,
    cv2.BORDER_CONSTANT,
    value=255
)

# ==============================
# OCR
# ==============================

text = ""

for psm in [10, 8, 13, 7, 6]:
    config = (
        f"--psm {psm} "
        "-c tessedit_char_whitelist=0123456789 "
        "-c classify_bln_numeric_mode=1"
    )

    result = pytesseract.image_to_string(
        digit,
        config=config
    ).strip()

    print(f"PSM {psm} RESULT: [{result}]")

    if result.isdigit():
        text = result
        break

print("\n==============================")
print("Selected ROI:")
print(f"X={x}, Y={y}, Width={w}, Height={h}")

print("\nOCR RESULT:")
print(text if text else "NOT DETECTED")

print("==============================")

cv2.imshow("Original Selected Area", cropped)
cv2.imshow("Digit For OCR", digit)

cv2.waitKey(0)
cv2.destroyAllWindows()
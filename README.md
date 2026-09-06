# APLOS Screen OCR

Multi-Machine Real-time Screen OCR Data Logger for Node-RED and Database.

---

## 🚀 Quick Run (Sirf 3 Files)

| File | Kaam (Purpose) |
| :--- | :--- |
| **`SET_AREA.bat`** | Screen par number ka box set karne ke liye. (Double click karein -> Mouse se number par box draw karein -> `ENTER` dabayein -> Terminal turant close ho jayega aur OCR chalu ho jayega). |
| **`START.bat`** | OCR ko background me silently start karne ke liye (Terminal khulte hi band ho jayega, screen par kuch nahi dikhega). |
| **`STOP.bat`** | Background me chal rahe OCR ko stop karne ke liye (Terminal khulte hi band ho jayega). |

---

## 📋 Data Files

* **`ocr_log.csv`** : Sabhi detected values ka real-time log (Date, Time, Machine, Value, Previous Value, API Status).
* **`ocr_debug.log`** : Background activity aur system diagnostics log.
* **`roi.json`** : Saved screen coordinates (X, Y, Width, Height).
* **`.env`** : Machine Name, Line Name aur Node-RED API Server settings.

---

## ⚙️ Node-RED & Database Setup

* **`node_red_flow.json`** : Node-RED flow file (Import karne ke liye).
* **`schema.sql`** : MySQL / MariaDB database table creation schema.
* **`NODE_RED_SETUP.md`** : Multi-machine server setup guide.

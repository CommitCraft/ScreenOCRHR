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

## 🛡️ 5-Minute Auto-Sync & Zero Data Loss Protection

* Sabhi readings sabse pehle local **`ocr_log.csv`** me permanently save hoti hain.
* Agar kabhi network ya Node-RED band ho jaye, ya koi reading `TIMEOUT` ho jaye (jaise pehle row 11 hui thi):
  * Wo reading local CSV me safe rehti hai.
  * System **har 5 minute me automatically `ocr_log.csv` ko scan karta hai**.
  * Jo bhi readings miss ya fail hui hoti hain, unhe unke **original capture timestamp** ke saath Node-RED API par post karta hai aur status ko `SENT` me update kar deta hai.
  * Isse production ka **ek bhi log miss nahi hota**.

---

## 📋 Data Files

* **`ocr_log.csv`** : Sabhi detected values ka real-time log (Date, Time, Machine, Value, Previous Value, API Status).
* **`ocr_debug.log`** : Background activity aur system diagnostics log.
* **`roi.json`** : Saved screen coordinates (X, Y, Width, Height).
* **`.env`** : Machine Name, Line Name, API Server aur Sync settings.

---

## ⚙️ Node-RED GET APIs (Data Audit & Missing Check)

Node-RED flow me 3 GET APIs di gayi hain jisse browser ya curl/Postman se check kiya ja sakta hai ki koi data miss to nahi hua:

### 1. Data Integrity Audit (`/api/screen-ocr/verify`)
* **URL:** `http://127.0.0.1:1880/api/screen-ocr/verify` (ya `?machine=MC-04`)
* **Kaam:** Node-RED me received total readings, latest value, latest timestamp aur audit status dikhata hai.
* **Missing Check:** Iska `total_readings_received` aur client ke `ocr_log.csv` ke row count ko match karke 100% confirm ho jata hai ki koi data miss nahi hua.
* **Sample Response:**
```json
{
  "status": "SUCCESS",
  "verification_check": "DATA_INTEGRITY_AUDIT",
  "summary": {
    "total_readings_received": 15,
    "latest_value": "730",
    "latest_timestamp": "2026-09-06 23:50:00",
    "earliest_timestamp": "2026-09-06 23:38:00",
    "machines_reporting": ["MC-04"]
  },
  "audit_result": "DATA_LOGGED_AND_VERIFIED"
}
```

### 2. Machine Live Health Status (`/api/screen-ocr/status`)
* **URL:** `http://127.0.0.1:1880/api/screen-ocr/status`
* **Kaam:** Har machine ka live status batata hai (`ONLINE_ACTIVE` ya `STALE_OFFLINE`), aakhiri reading kab aayi, kitne seconds pehle aayi.

### 3. Historical Received Logs (`/api/screen-ocr/logs`)
* **URL:** `http://127.0.0.1:1880/api/screen-ocr/logs?limit=50` (ya `?machine=MC-04&limit=20`)
* **Kaam:** Node-RED dwara receive ki gayi pichli readings ka pura array return karta hai taaki direct JSON check kiya ja sake.

---

## 🗄️ MySQL Direct SELECT Query APIs (Database Ground Truth)

Agar aapko direct MySQL Database se `SELECT` query chala ke check karna hai ki DB me kitna data store hai aur kaunsa miss hua:

### 1. Direct DB Audit & Verification (`/api/screen-ocr/db-verify`)
* **URL:** `http://127.0.0.1:1880/api/screen-ocr/db-verify?machine=MC-04`
* **Query:** `SELECT COUNT(*), MAX(captured_at), detected_value FROM machine_ocr_logs`
* **Response:**
```json
{
  "status": "SUCCESS",
  "source": "MYSQL_DATABASE_SELECT_QUERY",
  "machine_name": "MC-04",
  "total_db_records": 38,
  "last_db_captured_at": "2026-09-07 00:00:00",
  "last_db_value": "00"
}
```

### 2. Direct DB Logs Query (`/api/screen-ocr/db-logs`)
* **URL:** `http://127.0.0.1:1880/api/screen-ocr/db-logs?limit=20&machine=MC-04`
* **Query:** `SELECT * FROM machine_ocr_logs ORDER BY captured_at DESC LIMIT 20`
* **Response:** MySQL table me permanently store huye records ka direct JSON array.

---

## ⚙️ Node-RED & Database Setup

* **`node_red_flow.json`** : Node-RED flow file (POST + In-memory GET + MySQL Direct SELECT Query nodes).
* **`schema.sql`** : MySQL / MariaDB database table creation schema.
* **`NODE_RED_SETUP.md`** : Multi-machine server setup guide.

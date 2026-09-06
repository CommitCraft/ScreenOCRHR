# Screen OCR - Multi-Machine Node-RED & Database Setup Guide

Yeh guide aapko setup karne me help karegi taaki multiple machines se Screen OCR ka data Node-RED me aaye aur database (MySQL/MariaDB ya SQLite) me automatically store ho sake.

---

## 1. Database Setup (Tables Create Karein)

Sabse pehle apne Database Server (e.g. MySQL Workbench, phpMyAdmin, ya MySQL CLI) me `schema.sql` file run karein:

```bash
mysql -u root -p < schema.sql
```

Ya phir MySQL me yeh commands run karein:

```sql
CREATE DATABASE IF NOT EXISTS ocr_db;
USE ocr_db;

-- 1. Har machine ka continuous history log table
CREATE TABLE IF NOT EXISTS machine_ocr_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    machine_name VARCHAR(50) NOT NULL,
    line_name VARCHAR(50) NOT NULL,
    detected_value VARCHAR(50) NOT NULL,
    previous_value VARCHAR(50) DEFAULT NULL,
    captured_at DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_machine (machine_name),
    INDEX idx_line (line_name),
    INDEX idx_captured_at (captured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Har machine ka latest live status table (Dashboard ke liye)
CREATE TABLE IF NOT EXISTS machine_current_status (
    machine_name VARCHAR(50) PRIMARY KEY,
    line_name VARCHAR(50) NOT NULL,
    latest_value VARCHAR(50) NOT NULL,
    previous_value VARCHAR(50) DEFAULT NULL,
    last_updated DATETIME NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 2. Node-RED me MySQL Node Install Karna

Agar aapke Node-RED me MySQL node pehle se nahi hai:

1. Node-RED browser me open karein (`http://localhost:1880`).
2. Top-right corner me **Menu (3 lines)** par click karein -> **Manage palette**.
3. **Install** tab par click karein.
4. Search box me type karein: `node-red-node-mysql`
5. **Install** button par click karein.

*(Alternately, terminal se install karne ke liye: `npm install node-red-node-mysql`)*

---

## 3. Node-RED Flow Import Karna

1. `node_red_flow.json` file ko text editor ya Notepad me open karke uska pura content **Copy** kar lein.
2. Node-RED me top-right **Menu** -> **Import** par click karein.
3. Box me JSON paste karein aur **Import** par click karein.
4. Ek naya tab **"Screen OCR Multi-Machine DB"** create ho jayega.

---

## 4. Database Connection Set Karna

1. Flow me **"DB: Insert machine_ocr_logs"** node par double click karein.
2. **Database** field ke bagal me bane **Pencil icon (Edit)** par click karein.
3. Apne database ki details bharein:
   - **Host:** `127.0.0.1` (ya aapke DB server ka LAN IP)
   - **Port:** `3306`
   - **User:** `root` (ya aapka db username)
   - **Password:** aapka database password
   - **Database:** `ocr_db`
4. **Update** button dabayein, phir **Done** dabayein.
5. Top-right me **Deploy** button daba kar flow ko activate kar dein.

---

## 5. Multiple Machines Setup (`.env` Configuration)

Har machine ke Screen OCR folder me ek `.env` file hogi jisme us machine ka unique naam aur line set hoga:

### Machine 1 (`MC-01`, Line 1):
```env
MACHINE_NAME=MC-01
LINE_NAME=Line-01
API_IP=192.168.1.100       # Node-RED server ka IP
API_PORT=1880
API_ENDPOINT=/api/screen-ocr
API_TIMEOUT=3
```

### Machine 2 (`MC-02`, Line 1):
```env
MACHINE_NAME=MC-02
LINE_NAME=Line-01
API_IP=192.168.1.100       # Node-RED server ka IP
API_PORT=1880
API_ENDPOINT=/api/screen-ocr
API_TIMEOUT=3
```

### Machine 3 (`MC-03`, Line 2):
```env
MACHINE_NAME=MC-03
LINE_NAME=Line-02
API_IP=192.168.1.100       # Node-RED server ka IP
API_PORT=1880
API_ENDPOINT=/api/screen-ocr
API_TIMEOUT=3
```

---

## 6. Testing (Kaise Check Karein)

Aap PowerShell ya CMD se test kar sakte hain:

```powershell
curl -X POST http://localhost:1880/api/screen-ocr `
  -H "Content-Type: application/json" `
  -d '{"machine_name": "MC-TEST", "line_name": "Line-01", "value": "250", "previous_value": "240", "timestamp": "2026-09-06 22:30:00"}'
```

**Response:**
```json
{
  "status": "SUCCESS",
  "machine_name": "MC-TEST",
  "line_name": "Line-01",
  "detected_value": "250",
  "previous_value": "240",
  "received_at": "2026-09-06 22:30:00"
}
```

Aur Node-RED debug window me live message dikhega, aur database table `machine_ocr_logs` aur `machine_current_status` me row add ho jayegi!

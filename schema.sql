-- ============================================================
-- SCREEN OCR DATABASE SCHEMA (MySQL / MariaDB / PostgreSQL / SQLite)
-- ============================================================

-- ============================================================
-- 1. MYSQL / MARIADB SCHEMA
-- ============================================================

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS ocr_db;
USE ocr_db;

-- Table 1: Full Historical Log (Har machine ki har reading ka record)
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

-- Table 2: Live Current Status (Har machine ki sabse latest reading dashboard ke liye)
CREATE TABLE IF NOT EXISTS machine_current_status (
    machine_name VARCHAR(50) PRIMARY KEY,
    line_name VARCHAR(50) NOT NULL,
    latest_value VARCHAR(50) NOT NULL,
    previous_value VARCHAR(50) DEFAULT NULL,
    last_updated DATETIME NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
-- 2. SQLITE SCHEMA (Agar MySQL ki jagah local SQLite file use karni ho)
-- ============================================================
-- File: ocr_database.db
/*
CREATE TABLE IF NOT EXISTS machine_ocr_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_name TEXT NOT NULL,
    line_name TEXT NOT NULL,
    detected_value TEXT NOT NULL,
    previous_value TEXT,
    captured_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS machine_current_status (
    machine_name TEXT PRIMARY KEY,
    line_name TEXT NOT NULL,
    latest_value TEXT NOT NULL,
    previous_value TEXT,
    last_updated TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_logs_machine ON machine_ocr_logs(machine_name);
CREATE INDEX IF NOT EXISTS idx_logs_line ON machine_ocr_logs(line_name);
CREATE INDEX IF NOT EXISTS idx_logs_captured ON machine_ocr_logs(captured_at);
*/


-- ============================================================
-- 3. POSTGRESQL SCHEMA (Agar PostgreSQL use karna ho)
-- ============================================================
/*
CREATE TABLE IF NOT EXISTS machine_ocr_logs (
    id BIGSERIAL PRIMARY KEY,
    machine_name VARCHAR(50) NOT NULL,
    line_name VARCHAR(50) NOT NULL,
    detected_value VARCHAR(50) NOT NULL,
    previous_value VARCHAR(50),
    captured_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS machine_current_status (
    machine_name VARCHAR(50) PRIMARY KEY,
    line_name VARCHAR(50) NOT NULL,
    latest_value VARCHAR(50) NOT NULL,
    previous_value VARCHAR(50),
    last_updated TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pg_machine ON machine_ocr_logs(machine_name);
CREATE INDEX IF NOT EXISTS idx_pg_line ON machine_ocr_logs(line_name);
CREATE INDEX IF NOT EXISTS idx_pg_captured ON machine_ocr_logs(captured_at);
*/

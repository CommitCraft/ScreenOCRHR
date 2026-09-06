import os

def remove_from_startup():
    startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
    vbs_path = os.path.join(startup_dir, "ScreenOCR_AutoStart.vbs")
    bat_path = os.path.join(startup_dir, "ScreenOCR_AutoStart.bat")

    removed = False
    for path in [vbs_path, bat_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
                removed = True
                print(f"[OK] Removed: {os.path.basename(path)}")
            except Exception as e:
                print(f"[!] Error removing {os.path.basename(path)}: {e}")

    print("=" * 60)
    if removed:
        print("[SUCCESS] Screen OCR Auto-Start has been REMOVED.")
    else:
        print("[*] No Screen OCR Auto-Start entry found in Startup folder.")
    print("=" * 60)

if __name__ == "__main__":
    remove_from_startup()

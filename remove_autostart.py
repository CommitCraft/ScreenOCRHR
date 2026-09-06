import os

def remove_from_startup():
    startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
    batch_path = os.path.join(startup_dir, "ScreenOCR_AutoStart.bat")

    if os.path.exists(batch_path):
        try:
            os.remove(batch_path)
            print("=" * 60)
            print("[SUCCESS] Auto-Start has been REMOVED from Windows Startup.")
            print("=" * 60)
        except Exception as e:
            print(f"[!] Error removing startup entry: {e}")
    else:
        print("[*] Auto-Start entry was not found in Startup folder.")

if __name__ == "__main__":
    remove_from_startup()

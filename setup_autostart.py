import os
import sys

def install_to_startup():
    startup_dir = os.path.expandvars(
        r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    )

    script_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "live_ocr.py"
    )

    work_dir = os.path.dirname(script_path)

    # python.exe ki jagah pythonw.exe
    python_dir = os.path.dirname(sys.executable)
    pythonw_exe = os.path.join(python_dir, "pythonw.exe")

    if not os.path.exists(pythonw_exe):
        print("ERROR: pythonw.exe not found")
        return

    vbs_path = os.path.join(
        startup_dir,
        "ScreenOCR_AutoStart.vbs"
    )

    # 15 sec delay + completely hidden startup
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 15000
WshShell.CurrentDirectory = "{work_dir}"
WshShell.Run """{pythonw_exe}"" ""{script_path}""", 0, False
'''

    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(vbs_content)

    # Purana BAT startup remove kar do
    old_bat = os.path.join(
        startup_dir,
        "ScreenOCR_AutoStart.bat"
    )

    if os.path.exists(old_bat):
        try:
            os.remove(old_bat)
        except:
            pass

    print("=" * 60)
    print("SCREEN OCR SILENT AUTOSTART INSTALLED")
    print("=" * 60)
    print("Reboot ke baad:")
    print("- No CMD window")
    print("- No OCR preview")
    print("- No popup")
    print("- Saved ROI automatically use hogi")
    print("- OCR background me continuously chalega")
    print("=" * 60)


if __name__ == "__main__":
    install_to_startup()
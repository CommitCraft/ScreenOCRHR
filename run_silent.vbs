Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\ScreenOCR"
WshShell.Run """C:\Program Files\Python314\pythonw.exe"" ""C:\ScreenOCR\live_ocr.py""", 0, False

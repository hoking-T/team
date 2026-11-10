@echo off
cd /d "%~dp0"
set WMS_NO_BROWSER=0
if exist "D:\Python\python.exe" (
    "D:\Python\python.exe" app.py
) else (
    python app.py
)
pause

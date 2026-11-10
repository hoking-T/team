@echo off
cd /d "%~dp0"
java -version
if errorlevel 1 goto fail
if not exist "release\warehouse-1.0.0.jar" goto fail
echo Open http://127.0.0.1:8080 after Started WarehouseApplication appears.
echo Press Ctrl+C to stop. Data is saved in the data folder.
java -jar "release\warehouse-1.0.0.jar"
:fail
pause

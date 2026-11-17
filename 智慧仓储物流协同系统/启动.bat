@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem ---- 1. 若 8000 端口已有服务在跑，直接打开页面，不重复启动 ----
netstat -ano | findstr /C:"LISTENING" | findstr ":8000" >nul
if not errorlevel 1 goto openpage

rem ---- 2. 找一个可用的 Python 解释器 ----
set "PYEXE="
if exist "D:\Python\python.exe" set "PYEXE=D:\Python\python.exe"
if not defined PYEXE (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
        if exist "%%~fD\python.exe" set "PYEXE=%%~fD\python.exe"
    )
)
if not defined PYEXE (
    where python >nul 2>&1 && set "PYEXE=python"
)
if not defined PYEXE (
    where py >nul 2>&1 && set "PYEXE=py"
)
if not defined PYEXE (
    echo [错误] 未找到 Python，请先安装 Python 3，或把 python.exe 的路径写进本文件。
    pause
    exit /b 1
)

rem ---- 3. 启动服务（服务启动后会自己打开浏览器） ----
set WMS_NO_BROWSER=0
"%PYEXE%" app.py
goto end

:openpage
echo [提示] 检测到 8000 端口已有服务在运行，直接打开页面...
start "" "http://localhost:8000/"
ping -n 3 127.0.0.1 >nul

:end
pause

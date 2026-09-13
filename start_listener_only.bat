@echo off
REM Start ONLY the ANSA TCP listener on :9999.
REM Deliberately does NOT run "taskkill ansa_win64.exe": the user has a GUI
REM ANSA instance open (PID 21512) that must not be touched.
setlocal
set "ANSA_EXE=D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\ansa64.bat"
set "PWD=D:\ansa-tcp-bridge"
cd /d "D:\ansa-tcp-bridge"
if not exist "%ANSA_EXE%" echo [ERROR] ANSA launcher not found & exit /b 1
start "ANSA listener 9999" /min "%ANSA_EXE%" -nolauncher -listenport 9999 -foregr -b
exit /b 0

@echo off
REM ===========================================================================
REM  ANSA TCP listener launcher  (v6.2)
REM ---------------------------------------------------------------------------
REM  Starts ANSA in LISTENER mode on port 9999 for the ansa-tcp-bridge MCP
REM  server. Verified working 2026-09-10 on ANSA 25.1.4.
REM
REM  IMPORTANT - read this before you think it "did not open":
REM    * ANSA runs with "-b" (batch). There is deliberately NO ANSA GUI.
REM    * ANSA *does* open a console window of its own; v6.2 starts it MINIMISED
REM      so you are not misled by it. Its last line is normally
REM          "Code generation completed."
REM      and then it just SITS THERE WAITING for MCP commands. That idle pause
REM      is the healthy state, not a hang. Do not close it - closing it kills
REM      the listener.
REM    * Success is proven by the port line printed below, nothing else.
REM    * ANSA keeps running after this window closes; to stop the listener run
REM          taskkill /F /IM ansa_win64.exe
REM
REM  cmd.exe traps this file avoids on purpose (each cost us hours):
REM    1. `%ANSA_HOME%` contains "(x86)". Using it BARE inside an
REM       `if ... ( ... )` block makes cmd treat that ")" as the end of the
REM       block -> "was unexpected at this time" and the script dies
REM       instantly. Inside blocks we therefore use the delayed-expansion
REM       form "!ANSA_EXE!" wrapped in quotes.
REM    2. ANSA is a native Windows app; a Git-Bash style %PWD% ("/d/...")
REM       makes it print "Can not cd to PWD" and exit. %PWD% is scrubbed to
REM       a Windows path before launching.
REM    3. `timeout /t` errors out when stdin is redirected; `ping -n N` is
REM       used as the portable sleep instead.
REM
REM  Optional: pass a model to open at startup, e.g.
REM                  ansa_listener.bat "J:\path\to\model.ansa"
REM ===========================================================================

setlocal enabledelayedexpansion
set "ANSA_HOME=D:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\"
set "ANSA_EXE=%ANSA_HOME%ansa64.bat"
set "ANSA_PORT=9999"
set "WORKDIR=D:\ansa-tcp-bridge"

if not exist "%ANSA_EXE%" (
    echo [ERROR] ansa64.bat NOT FOUND at "!ANSA_EXE!"
    echo         Edit ANSA_HOME in this script.
    pause
    exit /b 1
)

set "PWD=%WORKDIR%"
cd /d "%WORKDIR%"
if not exist "%WORKDIR%\diag_out" mkdir "%WORKDIR%\diag_out"

echo ============================================================
echo   ANSA listener launcher (v6.2)
echo ------------------------------------------------------------
echo   Port   : %ANSA_PORT%
echo   Flags  : -nolauncher -listenport %ANSA_PORT% -foregr -b
echo   PWD    : %PWD%   (scrubbed to a Windows path)
echo ------------------------------------------------------------
echo   ANSA has NO GUI on purpose - no model window will appear.
echo   A console window WILL be opened MINIMISED (taskbar).
echo   Its "Code generation completed." line is the normal
echo   idle state, i.e. ANSA waiting for MCP commands.
echo ============================================================
echo.

echo [1/2] Stopping any previous ANSA instance ...
taskkill /F /T /IM ansa_win64.exe >nul 2>&1
ping -n 3 127.0.0.1 >nul

echo [2/2] Starting the listener ...
if "%~1"=="" (
    start "ANSA listener :%ANSA_PORT%" /min "!ANSA_EXE!" -nolauncher -listenport %ANSA_PORT% -foregr -b
) else (
    start "ANSA listener :%ANSA_PORT%" /min "!ANSA_EXE!" -nolauncher -listenport %ANSA_PORT% -foregr -b "%~1"
)

echo.
echo Waiting for port %ANSA_PORT% (up to 60s) ...
set OK=0
for /L %%i in (1,1,60) do (
    if !OK! EQU 0 (
        netstat -an | findstr ":%ANSA_PORT%" >nul
        if not errorlevel 1 (
            set OK=1
        ) else (
            ping -n 2 127.0.0.1 >nul
        )
    )
)

echo.
echo ------------------------------------------------------------
if "!OK!"=="1" (
    echo   [SUCCESS] ANSA listener is UP on port %ANSA_PORT%
    netstat -an | findstr ":%ANSA_PORT%"
    echo.
    echo   Next step : go to WorkBuddy and call the tool  ping_ansa
    echo   all 49 ansa-tcp tools are usable once the port is up
) else (
    echo   [FAILED] No listener on port %ANSA_PORT% after 60s.
    echo.
    echo   Checklist:
    echo     1. Another ANSA may still hold the port. Run
    echo        taskkill /F /IM ansa_win64.exe   then retry.
    echo     2. Look for "Can not cd to PWD" or a license error in the
    echo        minimised "ANSA listener :%ANSA_PORT%" console window.
    echo     3. Restore that minimised window from the taskbar - ANSA
    echo        prints its real error there.
)
echo ------------------------------------------------------------
echo.
echo ANSA keeps running even after you close this window.
echo To stop it, run:  taskkill /F /IM ansa_win64.exe
echo.
pause
endlocal

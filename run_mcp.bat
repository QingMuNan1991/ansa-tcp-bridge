@echo off
REM Launcher for ansa-tcp-bridge MCP server
REM Edit ANSA_SCRIPTS_PATH below to your ANSA install.

set "ANSA_SCRIPTS_PATH=C:\Program Files (x86)\BETA_CAE_Systems\ansa_v25.1.4\scripts"
set "ANSA_PORT=9999"
set "ANSA_HOST=localhost"

set "VENV_PY=C:\Users\Admin\.workbuddy\binaries\python\envs\ansa-tcp\Scripts\python.exe"
set "PKG_DIR=D:\ansa-tcp-bridge"

set "PYTHONPATH=%PKG_DIR%"

"%VENV_PY%" -m mcp_server.server %*

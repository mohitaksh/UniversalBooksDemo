@echo off
REM ═══════════════════════════════════════════════════════
REM UniversalBooks — Windows Install Script
REM ═══════════════════════════════════════════════════════
REM Usage:
REM   Double-click this file, or run in Command Prompt:
REM     install_windows.bat
REM
REM Prerequisites:
REM   - Python 3.11+ installed and added to PATH
REM   - ngrok downloaded and added to PATH (https://ngrok.com/download)
REM ═══════════════════════════════════════════════════════

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║   UniversalBooks — Windows Install                   ║
echo ╚══════════════════════════════════════════════════════╝
echo.

REM ── 1. Check Python ────────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo   ERROR: Python not found! Install from https://python.org
    echo   Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
python --version
echo   OK
echo.

REM ── 2. Create venv ─────────────────────────────────────
echo [2/5] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo   Created venv
) else (
    echo   venv already exists, skipping
)
echo.

REM ── 3. Activate and install deps ───────────────────────
echo [3/5] Installing Python dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
echo.

REM ── 4. Environment file ────────────────────────────────
echo [4/5] Setting up environment file...
if not exist ".env.local" (
    copy .env.example .env.local >nul
    echo   Created .env.local from .env.example
    echo   IMPORTANT: Edit .env.local and fill in your API keys!
) else (
    echo   .env.local already exists, skipping
)
echo.

REM ── 5. Create logs directory ───────────────────────────
echo [5/5] Creating logs directory...
if not exist "logs" mkdir logs
echo   logs\ directory ready
echo.

echo ╔══════════════════════════════════════════════════════╗
echo ║   Installation Complete!                             ║
echo ╠══════════════════════════════════════════════════════╣
echo ║                                                      ║
echo ║  Next steps:                                         ║
echo ║  1. Edit .env.local with your API keys               ║
echo ║  2. Open 3 terminals and run:                        ║
echo ║                                                      ║
echo ║     Terminal 1: venv\Scripts\activate                 ║
echo ║                 uvicorn server:app --reload --port 8000║
echo ║                                                      ║
echo ║     Terminal 2: venv\Scripts\activate                 ║
echo ║                 python main_agent.py dev              ║
echo ║                                                      ║
echo ║     Terminal 3: ngrok http 8000                       ║
echo ║                                                      ║
echo ╚══════════════════════════════════════════════════════╝
echo.
pause

@echo off
REM Quick setup script for Canvas Auto-Sync (Windows)

echo 🎯 Canvas Auto-Sync Setup
echo ==========================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.11 or higher.
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✓ Found Python %PYTHON_VERSION%

REM Create virtual environment
echo.
echo Creating virtual environment...
python -m venv .venv

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo Installing dependencies...
pip install -e .

REM Create .env file if it doesn't exist
if not exist .env (
    echo.
    echo Creating .env file from template...
    copy .env.example .env
    echo ⚠️  Please edit .env and add your Canvas API token!
    echo    Get your token from: Canvas → Settings → + New Access Token
)

REM Create directories
if not exist data mkdir data
if not exist logs mkdir logs

echo.
echo ✅ Setup complete!
echo.
echo Next steps:
echo 1. Edit .env and add your CANVAS_API_TOKEN
echo 2. Run: .venv\Scripts\activate
echo 3. Run: python scripts\sync_canvas.py
echo.
pause

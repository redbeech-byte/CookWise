@echo off
echo 🍳 Starting CookWise Setup for Windows...

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: Python is not installed or not in PATH.
    echo Please install it from python.org and ensure 'Add to PATH' is checked.
    pause
    exit /b
)

:: 2. Create Virtual Environment
if not exist "venv" (
    echo 📦 Creating virtual environment (venv)...
    python -m venv venv
)

:: 3. Activate and Install
call venv\Scripts\activate
echo 🛠️  Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

:: 4. Launch App
echo 🚀 Launching CookWise!
streamlit run main_app.py
pause

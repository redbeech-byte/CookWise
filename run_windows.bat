
@echo off
setlocal

echo Starting CookWise Setup for Windows...
echo.

REM Move into the folder where this batch file is located
cd /d "%~dp0"

REM 1. Check whether Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not available in PATH.
    echo Please install Python and make sure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

REM 2. Create a local virtual environment if it does not already exist
if not exist ".venv" (
    echo Creating local virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Error: Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

REM 3. Activate the virtual environment
call .venv\Scripts\activate
if errorlevel 1 (
    echo Error: Failed to activate the virtual environment.
    pause
    exit /b 1
)

REM 4. Upgrade pip inside the virtual environment
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Warning: pip upgrade failed. Continuing anyway...
)

REM 5. Install required packages
if not exist "requirements.txt" (
    echo Error: requirements.txt was not found in this folder.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install -r requirements_windows.txt
if errorlevel 1 (
    echo Error: Failed to install one or more dependencies from requirements_windows.txt.
    pause
    exit /b 1
)

REM 6. Check that Streamlit secrets exist
if not exist ".streamlit\secrets.toml" (
    echo Error: .streamlit\secrets.toml was not found.
    echo The application needs this file for API keys and Supabase credentials.
    pause
    exit /b 1
)

REM 7. Launch the app using the Python interpreter from the venv
echo Launching CookWise...
python -m streamlit run main_app.py

pause
endlocal

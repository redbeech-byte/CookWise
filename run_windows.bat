REM CookWise Windows startup script.
Rem This file creates/reuses a local virtual environment,
REM installs the Windows dependency file, checks for required secrets, and
REM then starts the Streamlit app.
Rem This allows for a one-click setup and launch of the app.
REM
REM Batch files use REM for comments. Using # here would make Windows try to
REM execute the line as a command, so all documentation in this file uses REM.

@echo off
setlocal

echo Starting CookWise Setup for Windows...
echo.

REM Running from the script folder makes relative paths predictable.
REM Without this, double-clicking the file from another folder could make
REM Python look for requirements and app files in the wrong place.
cd /d "%~dp0"

REM Checking Python early gives the user a clear setup error before any
REM virtual-environment or dependency commands are attempted.
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not available in PATH.
    echo Please install Python and make sure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

REM Creating the virtual environment only when it is missing keeps later runs
REM faster and preserves already-installed packages between launches.
if not exist ".venv" (
    echo Creating local virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Error: Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

REM Activating the environment makes the following python/pip commands use
REM CookWise's local packages instead of the system-wide Python installation.
call .venv\Scripts\activate
if errorlevel 1 (
    echo Error: Failed to activate the virtual environment.
    pause
    exit /b 1
)

REM Updating pip helps avoid installation issues caused by older package tools.
REM A failed pip upgrade is treated as a warning because dependency installation
REM may still work with the existing pip version.
echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Warning: pip upgrade failed. Continuing anyway...
)

REM CookWise keeps platform-specific dependency files because some packages can
REM differ between Windows and macOS/Linux.
if not exist "requirements_windows.txt" (
    echo Error: requirements_windows.txt was not found in this folder.
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

REM Streamlit secrets are not committed to the repository, but the app needs
REM them locally for API keys and Supabase credentials.
if not exist ".streamlit\secrets.toml" (
    echo Error: .streamlit\secrets.toml was not found.
    echo The application needs this file for API keys and Supabase credentials.
    pause
    exit /b 1
)

REM Launching through python -m ensures Streamlit runs from the active virtual
REM environment, even if another Streamlit installation exists globally.
echo Launching CookWise...
python -m streamlit run main_app.py

pause
endlocal

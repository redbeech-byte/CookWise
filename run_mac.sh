#!/bin/bash

# CookWise macOS/Linux startup script.
# This file gives non-Windows users a one-command way to prepare the local
# Python environment and launch the Streamlit app. It creates/reuses a virtual
# environment, installs the macOS/Linux dependency file, and starts CookWise.

# Starting message so the user knows the script is running after double-clicking
# or launching it from a terminal.
echo "🍳 Starting CookWise Setup..."

# Checking for python3 before creating the virtual environment gives a clear
# error instead of failing later with a less helpful command-not-found message.
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install it from python.org."
    exit 1
fi

# Creating the virtual environment only when it is missing keeps repeat launches
# faster and preserves packages that were already installed for CookWise.
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment (venv)..."
    python3 -m venv venv
fi

# Activating the environment makes pip and streamlit use CookWise's local
# packages instead of any system-wide Python packages.
source venv/bin/activate

# CookWise uses a platform-specific requirements file because dependency
# versions and installation behavior can differ between Windows and macOS/Linux.
echo "🛠️  Installing dependencies..."
pip install --upgrade pip
pip install -r requirements_mac.txt

# Streamlit is started from the active virtual environment so the app uses the
# dependencies installed above.
echo "🚀 Launching CookWise!"
streamlit run main_app.py

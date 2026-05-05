#!/bin/bash

# CookWise Setup Script for macOS/Linux

echo "🍳 Starting CookWise Setup..."

# 1. Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install it from python.org."
    exit 1
fi

# 2. Create Virtual Environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment (venv)..."
    python3 -m venv venv
fi

# 3. Activate venv
source venv/bin/activate

# 4. Install/Update requirements
echo "🛠️  Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Launch App
echo "🚀 Launching CookWise!"
streamlit run main_app.py

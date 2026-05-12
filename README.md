# CookWise

CookWise is a Streamlit application. This guide explains how to set up and run the application on your machine.

## Prerequisites
- [Python 3](https://www.python.org/downloads/) installed and added to your system's PATH.

## Running the Application

### macOS / Linux

We provide a convenient shell script to set up a virtual environment, install the dependencies, and start the app automatically.

1. Open your terminal and navigate to this folder.
2. In the terminal, run the setup script:
   ```bash
   sh run_mac.sh
   # or
   ./run_mac.sh
   ```

**Note:** The script will automatically create a `venv` folder for your virtual environment and install packages from `requirements_mac.txt`.

### Windows

We provide a batch file that prepares everything and starts the application for you.

1. Open File Explorer to this folder.
2. Double-click the `run_windows.bat` file to run it.

**Note:** The batch script requires a `.streamlit\secrets.toml` file to exist for API keys. It will create a `.venv` folder for your virtual environment and install packages from `requirements_windows.txt`.

### Manually Running the App

If you prefer to set things up manually, follow these steps:

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```
   Or use conda.

2. **Activate the virtual environment:**
   - **macOS/Linux:**
     ```bash
     source venv/bin/activate
     ```
   - **Windows:**
     ```bash
     venv\Scripts\activate
     ```

3. **Install dependencies:**
   - **macOS/Linux:**
     ```bash
     pip install -r requirements_mac.txt
     ```
   - **Windows:**
     ```bash
     pip install -r requirements_windows.txt
     ```

4. **Ensure secrets are set up:**
   Create a `.streamlit/secrets.toml` file matching your configuration requirements.

5. **Run the Streamlit app:**
   ```bash
   streamlit run main_app.py
   ```

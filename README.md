# Lua minifier for stormworks

My simple tool to minify lua scripts when 8k symbols is not enought. Works both on Windows and Linux.

## Features

- Dependency-free (besides Python itself)
- Simple GUI using Tkinter
- Runs on both Windows and Linux
- Requires Python 3.11 or higher

## Requirements

- Python 3.11+
- Tkinter (usually included by default in Python installations)

No additional libraries or packages are required.

---

## Installation & Running

### Windows

You have two options to run the app on Windows:

1. Using Python directly  
   - If Python 3.11+ is installed, simply double-click `src/main.py` in downloaded source, or run:

   python src\main.py

2. Using the pre-built executable  
   - Download the latest `.exe` from the Releases page.  
   - Double-click the `.exe` to launch the app — no Python installation required.

---

### Linux

1. Ensure Python 3.11+ is installed:

python3 --version

2. Clone or download the repository:

git clone https://github.com/USERNAME/REPO.git
cd REPO

3. Run the app:

python3 src/main.py

Tkinter is usually included in default Python distributions on Linux. No extra dependencies are required.

---

## Usage

- Launch the application by running `main.py` or the `.exe` (on Windows).  
- Copy your script inside left text box.
- Press 'Minify'.
- Copy-paste minified script inside your stormworks microcontroller.

---

## Supported Platforms

- Windows  
- Linux
- Basically everything with python3.11+ with tkinter

---

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).  
You can redistribute it and/or modify it under the terms of the GPL-3.0 license.

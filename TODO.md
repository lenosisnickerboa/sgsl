# Host workshop maps and collections

# Status line
Installing... Updating... Started game server... Game server running...

# Fatal exit dialogue
Should show a dialog box stating what happened and then exit the application

# Compact and full widgets
Compact in shortcuts and full in config

# All widgets have status
Disable widgets when e.g. updating -> disable start, when started -> disable update...

# Config tab all
Showing all config items

# Add "Create an error report" functionality

# Open terminal without hiding sgsl window

# Source code formatting

# Forced save config (otherwise done on exit only)

# Restart program after install done. 

Consider adding a disabled restart button which is enabled when the install finishes successfully.

import subprocess
import sys

def restart_program():
    subprocess.Popen([sys.executable] + sys.argv)
    sys.exit(0)

---

# Map groups

# Add map images

# Add map group images


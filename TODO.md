# Host workshop maps and collections

# Fatal exit dialogue
Should show a dialog box stating what happened and then exit the application

# Add "Create an error report" functionality

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


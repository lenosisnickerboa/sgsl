# Install/Update game functionality

Add checkbuttons, make them work as terminal...

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

# Support workshop maps


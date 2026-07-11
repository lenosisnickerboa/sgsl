# Forced save config (otherwise done on exit only)

# Update game functionality (same as install?)

Add a checkbutton, make it work as terminal...

# Source code formatting

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


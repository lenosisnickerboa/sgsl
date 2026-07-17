"""
restart_application.py

Restarts the current process in place: replaces it with a fresh
instance of itself (same interpreter/executable, same arguments)
rather than spawning a child and exiting separately.

sys.argv[0] must be kept, not dropped: when running as
`python src/sgsl.py`, sys.executable is just the interpreter (e.g.
python.exe) and sys.argv[0] is the separate script path it needs to
be told to run — dropping it launches a bare interpreter with no
script at all, which is why this didn't work under VS Code's default
"run Python file" launch. For a frozen sgsl.exe, sys.executable
already is the whole program, so argv[0] there is just a redundant
(harmless) copy of its own path.
"""

import os
import sys


def restart_application() -> None:
    """Replace the current process with a new instance of itself."""
    # For a frozen (PyInstaller onefile) build, this tells the
    # bootloader that the new process is a fresh, independent instance
    # rather than a worker sub-process of this one. Without it, the new
    # process reuses/tracks this one's extracted _MEIPASS temp
    # directory and races its cleanup on exit, crashing with a
    # FileNotFoundError for base_library.zip. No effect when running
    # unfrozen (`python src/sgsl.py`).
    os.environ["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    os.execv(sys.executable, [sys.executable] + sys.argv)

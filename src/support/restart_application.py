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
    os.execv(sys.executable, [sys.executable] + sys.argv)

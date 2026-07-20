import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """Resolve a path to a bundled resource (e.g. under app/assets),
    relative to sys._MEIPASS when frozen by PyInstaller (see the
    matching `datas` entry in sgsl.spec), or relative to src/ when
    running from source."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative_path

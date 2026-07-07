from pathlib import Path


def get(dir: str) -> str:
    return Path(dir) / "game" / "bin" / "win64" / "cs2.exe"

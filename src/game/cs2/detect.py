from pathlib import Path


def detect(dir: str) -> bool:
    return (Path(dir) / "game" / "bin" / "win64" / "cs2.exe").is_file()

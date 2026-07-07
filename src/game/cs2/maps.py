from pathlib import Path


def get(root_dir: str) -> list[str]:
    return [p.stem for p in (Path(root_dir) / "game" / "csgo" / "maps").glob("*.vpk")]

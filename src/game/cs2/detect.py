from pathlib import Path
import game.cs2.runner

def is_installed(dir: str) -> bool:
    return (game.cs2.runner.get(dir)).is_file()

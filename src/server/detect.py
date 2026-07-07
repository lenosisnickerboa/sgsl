import game.cs2.detect

def detect(dir: str) -> str:
    if game.cs2.detect.is_installed(dir):
        return "cs2"
    return ""

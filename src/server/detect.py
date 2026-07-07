import game.cs2.detect

def detect(dir: str) -> str:
    if game.cs2.detect.detect(dir):
        return "cs2"
    return ""

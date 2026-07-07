name_mappings = {
    "cs2": "Counter-Strike 2",
    "csgo": "Counter-Strike Global Offensive",
    "vu": "Venice Unleashed"
}

def short_name(long_name: str) -> str:
    for short, long in name_mappings.items():
        if long == long_name:
            return short
    return ""

def long_name(short_name: str) -> str:
    return name_mappings.get(short_name, "") 

def is_valid_long_name(name: str) -> bool:
    return name in name_mappings.values()

def get_all_short_names() -> list:
    return list(name_mappings.keys())

def get_all_long_names() -> list:
    return list(name_mappings.values()) 

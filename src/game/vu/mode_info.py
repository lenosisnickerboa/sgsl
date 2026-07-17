class ModeInfo:
    """Lookup table between Venice Unleashed/Battlefield 3 game mode
    display names and their internal mode ids (e.g. "Conquest" <->
    "ConquestSmall0")."""

    _name_to_id: dict[str, str] = {
        "Conquest 64": "ConquestLarge0",
        "Conquest": "ConquestSmall0",
        "Conquest Assault 64": "ConquestAssaultLarge0",
        "Conquest Assault": "ConquestAssaultSmall0",
        "Conquest Assault: Day 2": "ConquestAssaultSmall1",
        "Rush": "RushLarge0",
        "Squad Rush": "SquadRush0",
        "Squad Deathmatch": "SquadDeathMatch0",
        "Team Deathmatch": "TeamDeathMatch0",
        "Team DM Close Quarters": "TeamDeathMatchC0",
        "Conquest Domination": "Domination0",
        "Gun Master": "GunMaster0",
        "Tank Superiority": "TankSuperiority0",
        "Scavenger": "Scavenger0",
        "Capture the Flag": "CaptureTheFlag0",
        "Air Superiority": "AirSuperiority0",
    }

    _id_to_name: dict[str, str] = {v: k for k, v in _name_to_id.items()}

    @classmethod
    def name_from_id(cls, id: str) -> str:
        return cls._id_to_name[id]

    @classmethod
    def id_from_name(cls, name: str) -> str:
        return cls._name_to_id[name]

    @classmethod
    def all_names(cls) -> list[str]:
        return list(cls._name_to_id.keys())

    @classmethod
    def all_ids(cls) -> list[str]:
        return list(cls._name_to_id.values())

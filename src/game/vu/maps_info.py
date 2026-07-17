class MapsInfo:
    """Lookup table between Venice Unleashed/Battlefield 3 map display
    names and their internal level ids (e.g. "Grand Bazaar" <-> "MP_001")."""

    _name_to_id: dict[str, str] = {
        "Grand Bazaar": "MP_001",
        "Teheran Highway": "MP_003",
        "Caspian Border": "MP_007",
        "Seine Crossing": "MP_011",
        "Operation Firestorm": "MP_012",
        "Damavand Peak": "MP_013",
        "Noshahr Canals": "MP_017",
        "Kharg Island": "MP_018",
        "Operation Metro": "MP_Subway",
        "Strike at Karkand": "XP1_001",
        "Gulf of Oman": "XP1_002",
        "Sharqi Peninsula": "XP1_003",
        "Wake Island": "XP1_004",
        "Donya Fortress": "XP2_Palace",
        "Operation 925": "XP2_Office",
        "Scrapmetal": "XP2_Factory",
        "Ziba Tower": "XP2_Skybar",
        "Alborz Mountains": "XP3_Alborz",
        "Armored Shield": "XP3_Shield",
        "Bandar Desert": "XP3_Desert",
        "Death Valley": "XP3_Valley",
        "Azadi Palace": "XP4_Parl",
        "Epicenter": "XP4_Quake",
        "Markaz Monolith": "XP4_FD",
        "Talah Market": "XP4_Rubble",
        "Operation Riverside": "XP5_001",
        "Nebandan Flats": "XP5_002",
        "Kiasar Railroad": "XP5_003",
        "Sabalan Pipeline": "XP5_004",
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

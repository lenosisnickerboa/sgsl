from config.toml_config import Config, IndexT


def build_shortcuts(master, shortcuts: list[IndexT], config: Config[IndexT]):
    for shortcut in shortcuts:
        config_item = config[shortcut]

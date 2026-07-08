"""
toml_handler.py

A small helper class for loading, merging, and persisting TOML config files.

Behavior:
- If the target file does not exist, it's created using the supplied defaults.
- If it exists, its contents are read and merged on top of the defaults
  (i.e. values found in the file take precedence over the defaults, but keys
  present only in the defaults are preserved).
- Nested dicts (TOML tables) are merged recursively rather than replaced wholesale.
"""

import copy
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # pip install tomli (for Python < 3.11)

import tomli_w  # pip install tomli-w  (writing is not in the stdlib)


class TomlHandler:
    def __init__(self, filepath, defaults=None):
        """
        Parameters
        ----------
        filepath : str | Path
            Full path to the TOML config file.
        defaults : dict, optional
            Default configuration values. Used as-is if the file doesn't
            exist yet, or as a fallback for any keys missing from the file.
        """
        self.filepath = Path(filepath)
        self.defaults = defaults or {}

        if not self.filepath.exists():
            self.config = copy.deepcopy(self.defaults)
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.write()
        else:
            file_data = self._read()
            self.config = self._merge(copy.deepcopy(self.defaults), file_data)

    def _read(self):
        with open(self.filepath, "rb") as f:
            return tomllib.load(f)

    def _merge(self, base, override):
        """Recursively merge `override` into `base`, returning `base`."""
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._merge(base[key], value)
            else:
                base[key] = value
        return base

    def get(self):
        """Return the full configuration dict."""
        return self.config

    def write(self):
        """Write the current in-memory config back to the TOML file."""
        with open(self.filepath, "wb") as f:
            tomli_w.dump(self.config, f)


if __name__ == "__main__":
    # Example usage
    defaults = {
        "app": {"name": "MyApp", "debug": False},
        "server": {"host": "0.0.0.0", "port": 8080},
    }

    handler = TomlHandler("/tmp/example_config.toml", defaults)
    config = handler.get()
    print(config)

    # Modify and persist a value
    config["server"]["port"] = 9090
    handler.write()
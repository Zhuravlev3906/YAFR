import tomllib
from pathlib import Path
from typing import Any, BinaryIO

from yafr.config.defaults import CONFIG_TEMPLATE


class ConfigLoader:
    def __init__(self, config_file: str | Path = "config.toml") -> None:
        self.config_file = Path(config_file)

    def read_config_file(self, *, create_missing: bool = True) -> dict[str, Any]:
        """Load TOML settings, creating defaults if the file is missing."""
        try:
            file = self.config_file.open("rb")
        except FileNotFoundError:
            if not create_missing:
                raise
            try:
                with self.config_file.open("x", encoding="utf-8") as default_file:
                    default_file.write(CONFIG_TEMPLATE)
            except FileExistsError:
                pass
            file = self.config_file.open("rb")

        with file:
            return self.get_toml(file)

    def get_toml(self, file: BinaryIO) -> dict[str, Any]:
        return tomllib.load(file)

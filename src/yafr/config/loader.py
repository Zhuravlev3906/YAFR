import tomllib
from pathlib import Path
from typing import Any, BinaryIO


class ConfigLoader:
    def __init__(self, config_file: str | Path = "config.toml") -> None:
        self.config_file = Path(config_file)
        self._base_config = """
# Default settings.

[general]
# Include subfolders.
recursive = false
# Include names starting with a dot.
include_hidden = false

[sort]
# Defaults to the source folder.
# Relative paths start from this config's folder.
# output = "./sorted"

# Folder for unknown or missing extensions.
# Comment out to leave these files in place.
fallback = "other"

# No leading dots. Each extension belongs to one group.
[sort.groups]
images = ["jpg", "jpeg", "png", "webp", "heic"]
videos = ["mp4", "mkv", "mov"]
documents = ["pdf", "txt", "docx"]
archives = ["zip", "7z", "tar.gz"]

[rename]
# The extension is added automatically.
# Examples: "{n:03d}", "S{season:02d}E{episode:02d}".
pattern = "{n}"
start = 1
season = 1
"""

    def read_config_file(self, *, create_missing: bool = True) -> dict[str, Any]:
        """Load TOML settings, creating defaults if the file is missing."""
        try:
            file = self.config_file.open("rb")
        except FileNotFoundError:
            if not create_missing:
                raise
            try:
                with self.config_file.open("x", encoding="utf-8") as default_file:
                    default_file.write(self._base_config.lstrip())
            except FileExistsError:
                pass
            file = self.config_file.open("rb")

        with file:
            return self.get_toml(file)

    def get_toml(self, file: BinaryIO) -> dict[str, Any]:
        return tomllib.load(file)

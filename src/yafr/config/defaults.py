"""Shared sorting defaults and the configuration file template."""

import tomllib
from importlib.resources import files

CONFIG_TEMPLATE = (
    files("yafr.config").joinpath("template.toml").read_text(encoding="utf-8")
)
_GROUPS: dict[str, list[str]] = tomllib.loads(CONFIG_TEMPLATE)["sort"]["groups"]


def default_sort_groups() -> dict[str, list[str]]:
    """Return independent groups for each configuration instance."""
    return {name: extensions.copy() for name, extensions in _GROUPS.items()}

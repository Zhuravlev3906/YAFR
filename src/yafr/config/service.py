from copy import deepcopy
from pathlib import Path
from typing import Any

from platformdirs import user_config_path
from pydantic import ValidationError

from yafr.config.loader import ConfigLoader
from yafr.config.validator import Config


class ConfigError(ValueError):
    """Configuration could not be loaded or validated."""


def _resolve_output(data: dict[str, Any], base: Path) -> None:
    section = data.get("sort")
    if isinstance(section, dict) and section.get("output") is not None:
        output = Path(section["output"]).expanduser()
        section["output"] = str((base / output).resolve())


def load_config(
    config_file: str | Path | None = None,
    *,
    overrides: dict[str, Any] | None = None,
) -> Config:
    """Load validated settings. Overrides contain only explicitly set CLI values.

    Relative file paths use the config folder; override paths use the current
    folder. Override sections merge by field, but groups are replaced in full.
    Reading settings never creates files or directories.
    """
    source = str(config_file) if config_file is not None else "user configuration"
    try:
        path = (
            Path(config_file).expanduser()
            if config_file is not None
            else user_config_path("yafr", appauthor=False) / "config.toml"
        ).absolute()
        source = str(path)
        try:
            data = ConfigLoader(path).read_config_file(create_missing=False)
        except FileNotFoundError:
            if config_file is not None:
                raise
            data = {}

        # Check the file before overrides can hide invalid settings.
        Config.model_validate(data)
        _resolve_output(data, path.parent)

        if overrides is not None:
            source = "CLI overrides"
            cli_data = deepcopy(overrides)
            Config.model_validate(cli_data)
            _resolve_output(cli_data, Path.cwd())
            for key, value in cli_data.items():
                if isinstance(value, dict) and isinstance(data.get(key), dict):
                    data[key] = {**data[key], **value}
                else:
                    data[key] = value

        return Config.model_validate(data)
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            details = "; ".join(
                f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
                for error in exc.errors(include_url=False)
            )
        else:
            details = str(exc)
        raise ConfigError(f"Invalid configuration ({source}): {details}") from exc

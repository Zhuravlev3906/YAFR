import re
from string import Formatter

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _check_name(value: str) -> str:
    if not value.strip() or value in {".", ".."}:
        raise ValueError("Name must not be empty, '.' or '..'")
    if any(char in value for char in "/\\\0:"):
        raise ValueError("Name must not contain path separators, ':' or null bytes")
    return value


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)


class GeneralConfig(_ConfigModel):
    recursive: bool = False
    include_hidden: bool = False


class SortConfig(_ConfigModel):
    output: str | None = None
    fallback: str | None = None
    groups: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "images": ["jpg", "jpeg", "png", "webp", "heic"],
            "videos": ["mp4", "mkv", "mov"],
            "documents": ["pdf", "txt", "docx"],
            "archives": ["zip", "7z", "tar.gz"],
        }
    )

    @field_validator("output")
    @classmethod
    def validate_output(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\0" in value):
            raise ValueError("Output must be a non-empty path without null bytes")
        return value

    @field_validator("fallback")
    @classmethod
    def validate_fallback(cls, value: str | None) -> str | None:
        return _check_name(value) if value is not None else None

    @field_validator("groups")
    @classmethod
    def validate_groups(cls, groups: dict[str, list[str]]) -> dict[str, list[str]]:
        normalized: dict[str, list[str]] = {}
        seen: set[str] = set()
        for name, extensions in groups.items():
            _check_name(name)
            normalized[name] = []
            for extension in extensions:
                extension = extension.casefold()
                if (
                    not extension
                    or any(not part for part in extension.split("."))
                    or any(char.isspace() or char in "/\\\0:" for char in extension)
                ):
                    raise ValueError(
                        f"Invalid extension {extension!r} in group {name!r}"
                    )
                if extension in seen:
                    raise ValueError(f"Duplicate extension: {extension!r}")
                seen.add(extension)
                normalized[name].append(extension)
        return normalized


class RenameConfig(_ConfigModel):
    pattern: str = "{n}"
    start: int = Field(default=1, ge=1)
    season: int = Field(default=1, ge=1)

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, pattern: str) -> str:
        for _, field, format_spec, conversion in Formatter().parse(pattern):
            if field is None:
                continue
            format_spec = format_spec or ""
            if field not in {"n", "season", "episode"}:
                raise ValueError(f"Unknown pattern field: {field!r}")
            if (
                conversion is not None
                or re.fullmatch(r"(?:0[1-9][0-9]*d)?", format_spec) is None
            ):
                raise ValueError("Use plain fields or zero padding, such as {n:03d}")
            if format_spec and int(format_spec[1:-1]) > 255:
                raise ValueError("Padding width must not exceed 255")
        _check_name(pattern.format(n=1, season=1, episode=1))
        return pattern


class Config(_ConfigModel):
    """Validate the dictionary returned by ConfigLoader.read_config_file()."""

    version: int = Field(default=1, ge=1, le=1)
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    sort: SortConfig = Field(default_factory=SortConfig)
    rename: RenameConfig = Field(default_factory=RenameConfig)

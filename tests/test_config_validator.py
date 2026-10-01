import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from yafr.config.loader import ConfigLoader
from yafr.config.validator import Config


class ConfigValidatorTests(unittest.TestCase):
    def test_loader_defaults_are_valid(self) -> None:
        with TemporaryDirectory() as directory:
            data = ConfigLoader(Path(directory) / "config.toml").read_config_file()
        config = Config.model_validate(data)
        self.assertEqual(config.version, 1)
        self.assertEqual(config.sort.fallback, "other")
        self.assertEqual(config.rename.start, 1)

    def test_partial_config_uses_independent_defaults(self) -> None:
        first = Config.model_validate({"rename": {"start": 5}})
        second = Config.model_validate({})
        first.sort.groups["images"].append("test-only-extension")
        self.assertNotIn("test-only-extension", second.sort.groups["images"])
        self.assertEqual(first.rename.start, 5)
        self.assertFalse(first.general.recursive)
        self.assertIsNone(first.sort.fallback)

    def test_groups_replace_defaults_and_normalize_extensions(self) -> None:
        data = {"sort": {"groups": {"custom": ["JPG", "tar.GZ"]}}}
        config = Config.model_validate(data)
        self.assertEqual(config.sort.groups, {"custom": ["jpg", "tar.gz"]})
        self.assertEqual(data["sort"]["groups"]["custom"], ["JPG", "tar.GZ"])

    def test_valid_patterns(self) -> None:
        for pattern in ("{n}", "{n:03d}", "S{season:02d}E{episode:02d}"):
            with self.subTest(pattern=pattern):
                config = Config.model_validate({"rename": {"pattern": pattern}})
                self.assertEqual(config.rename.pattern, pattern)

    def test_invalid_settings(self) -> None:
        cases = [
            {"unknown": True},
            {"version": 2},
            {"version": True},
            {"general": {"recursive": "false"}},
            {"general": {"recursive": 1}},
            {"rename": {"start": 0}},
            {"rename": {"season": True}},
            {"rename": {"season": "1"}},
            {"rename": {"typo": 1}},
            {"sort": {"output": ""}},
            {"sort": {"fallback": "../outside"}},
            {"sort": {"groups": {"../outside": ["jpg"]}}},
            {"sort": {"groups": {"images": [".jpg"]}}},
            {"sort": {"groups": {"images": ["jpg", "JPG"]}}},
            {"sort": {"groups": {"a": ["jpg"], "b": ["JPG"]}}},
        ]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                Config.model_validate(data)

    def test_invalid_patterns(self) -> None:
        for pattern in (
            "",
            "..",
            "../{n}",
            "{name}",
            "{n.real}",
            "{n[0]}",
            "{n!r}",
            "{n:{season}}",
            "{n:999d}",
            "{n:0999d}",
            "{n",
        ):
            with self.subTest(pattern=pattern), self.assertRaises(ValidationError):
                Config.model_validate({"rename": {"pattern": pattern}})

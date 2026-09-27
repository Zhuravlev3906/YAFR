import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from yafr.config import Config, ConfigError, load_config


class ConfigServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.path = self.root / "config.toml"

    def write_config(self, content: str) -> None:
        self.path.write_text(content, encoding="utf-8")

    def test_file_is_loaded_and_validated(self) -> None:
        self.write_config('[rename]\npattern = "{n:03d}"\nstart = 5\n')
        config = load_config(self.path)
        self.assertIsInstance(config, Config)
        self.assertEqual(config.rename.start, 5)
        self.assertEqual(config.rename.pattern, "{n:03d}")
        self.assertFalse(config.general.recursive)

    def test_missing_default_has_no_side_effects(self) -> None:
        folder = self.root / "absent"
        with patch("yafr.config.service.user_config_path", return_value=folder):
            self.assertEqual(load_config(), Config())
        self.assertFalse(folder.exists())

    def test_default_file_is_used(self) -> None:
        self.write_config("[general]\nrecursive = true\n")
        with patch("yafr.config.service.user_config_path", return_value=self.root):
            self.assertTrue(load_config().general.recursive)

    def test_explicit_missing_file_is_an_error(self) -> None:
        with self.assertRaises(ConfigError):
            load_config(self.path)
        self.assertFalse(self.path.exists())

    def test_invalid_files_are_not_modified(self) -> None:
        for content in ("[broken", "version = 2", "[general]\nrecursive = 1"):
            with self.subTest(content=content):
                self.write_config(content)
                with self.assertRaises(ConfigError) as caught:
                    load_config(self.path)
                self.assertIn(str(self.path), str(caught.exception))
                self.assertEqual(self.path.read_text(encoding="utf-8"), content)

    def test_error_identifies_field(self) -> None:
        self.write_config("[rename]\nstart = 0")
        with self.assertRaisesRegex(ConfigError, r"rename\.start"):
            load_config(self.path)

    def test_cli_overrides_merge_fields_and_replace_groups(self) -> None:
        self.write_config(
            "[general]\nrecursive = true\ninclude_hidden = true\n"
            '[sort.groups]\nimages = ["jpg"]\n'
            "[rename]\nstart = 4\nseason = 2\n"
        )
        overrides = {
            "general": {"recursive": False},
            "sort": {"groups": {"video": ["MKV"]}},
            "rename": {"start": 8},
        }
        config = load_config(self.path, overrides=overrides)
        self.assertFalse(config.general.recursive)
        self.assertTrue(config.general.include_hidden)
        self.assertEqual(config.rename.start, 8)
        self.assertEqual(config.rename.season, 2)
        self.assertEqual(config.sort.groups, {"video": ["mkv"]})
        self.assertEqual(overrides["sort"], {"groups": {"video": ["MKV"]}})

    def test_output_paths_use_their_own_base(self) -> None:
        self.write_config('[sort]\noutput = "file-output"\n')
        self.assertEqual(
            load_config(self.path).sort.output, str(self.root / "file-output")
        )
        overrides = {"sort": {"output": "cli-output"}}
        config = load_config(self.path, overrides=overrides)
        self.assertEqual(config.sort.output, str(Path.cwd() / "cli-output"))
        self.assertEqual(overrides["sort"]["output"], "cli-output")
        self.assertFalse((self.root / "file-output").exists())

    def test_invalid_cli_and_file_settings_cannot_be_hidden(self) -> None:
        self.write_config("[general]\nrecursive = true")
        with self.assertRaisesRegex(ConfigError, "CLI overrides"):
            load_config(self.path, overrides={"general": {"recursive": "false"}})
        self.write_config("[general]\nrecursive = 1")
        with self.assertRaises(ConfigError):
            load_config(self.path, overrides={"general": {"recursive": False}})

    def test_read_errors_are_wrapped(self) -> None:
        with (
            patch(
                "yafr.config.service.ConfigLoader.read_config_file",
                side_effect=PermissionError("Access denied"),
            ),
            self.assertRaisesRegex(ConfigError, "Access denied"),
        ):
            load_config(self.path)
        self.path.write_bytes(b"\xff")
        with self.assertRaises(ConfigError):
            load_config(self.path)

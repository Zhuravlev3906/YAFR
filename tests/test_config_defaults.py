from pathlib import Path

import pytest

from yafr.app import prepare_operation, run_operation
from yafr.config import Config, load_config
from yafr.config.defaults import CONFIG_TEMPLATE
from yafr.config.loader import ConfigLoader


def test_example_generated_config_and_builtin_groups_match(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "examples" / "config.toml"
    assert example.read_text(encoding="utf-8") == CONFIG_TEMPLATE
    generated = tmp_path / "config.toml"
    config = Config.model_validate(ConfigLoader(generated).read_config_file())
    assert generated.read_text(encoding="utf-8") == CONFIG_TEMPLATE
    assert (
        load_config(example).sort.groups == config.sort.groups == Config().sort.groups
    )
    assert config.sort.fallback == "other"
    assert Config().sort.fallback is None


@pytest.mark.parametrize(
    ("filename", "category"),
    [
        ("photo.AVIF", "images"),
        ("photo.CR3", "raw_images"),
        ("drawing.kra", "design"),
        ("clip.m2ts", "videos"),
        ("book.m4b", "audio"),
        ("music.m3u8", "playlists"),
        ("captions.vtt", "subtitles"),
        ("notes.md", "documents"),
        ("table.csv", "spreadsheets"),
        ("slides.pptx", "presentations"),
        ("book.fb2.zip", "ebooks"),
        ("backup.tar.zst", "archives"),
        ("disk.img.xz", "disk_images"),
        ("package.whl", "installers"),
        ("types.d.ts", "code"),
        ("table.csv.gz", "data"),
        ("settings.yaml", "configs"),
        ("database.sqlite3", "databases"),
        ("font.woff2", "fonts"),
        ("mesh.obj", "models_3d"),
        ("drawing.step", "cad"),
        ("map.osm.pbf", "gis"),
        ("scan.NII.GZ", "scientific"),
        ("letter.eml", "email"),
        ("contact.vcf", "contacts"),
        ("event.ics", "calendars"),
        ("download.torrent", "torrents"),
        ("certificate.pem", "security"),
        ("application.log.gz", "logs"),
    ],
)
def test_default_categories_sort_and_preserve_rename_suffixes(
    tmp_path: Path, filename: str, category: str
) -> None:
    config = tmp_path / "config.toml"
    config.write_text("version = 1\n", encoding="utf-8")
    source = tmp_path / "files"
    source.mkdir()
    original = source / filename
    original.write_bytes(b"unchanged contents")

    rename = prepare_operation("rename", source, config_file=config)
    assert (
        rename.plan.operations[0].destination.name == "1." + filename.split(".", 1)[1]
    )
    sort = prepare_operation("sort", source, config_file=config)
    destination = source / category / filename
    assert sort.plan.operations[0].destination == destination
    assert run_operation(sort).successful
    assert original.exists() and not destination.exists()
    assert run_operation(sort, apply=True).successful
    assert destination.read_bytes() == b"unchanged contents"
    assert not original.exists()

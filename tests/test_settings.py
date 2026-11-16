"""Settings migration and failure recovery at the filesystem boundary."""

import json
from dataclasses import replace

import pytest

from yt.domain.settings import AppSettings
from yt.infrastructure.settings import JsonSettingsRepository


def test_legacy_settings_and_unknown_fields_are_preserved(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "folder": "D:/Музыка",
                "quality": "320",
                "volume": 0.27,
                "shuffle": True,
                "future_option": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )
    store = JsonSettingsRepository(path)
    settings = store.load()
    assert settings.folder == "D:/Музыка"
    assert settings.volume == 0.27
    store.save(replace(settings, concurrency=6))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["future_option"] == {"enabled": True}
    assert saved["concurrency"] == 6
    assert saved["quality"] == "320"


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {"volume": "nan", "concurrency": -3, "quality": "bad"},
        {"volume": None, "concurrency": {}, "folder": "\x00bad"},
    ],
)
def test_invalid_settings_use_safe_defaults(data):
    settings = AppSettings.from_mapping(data)
    assert settings.volume == 0.5
    assert settings.concurrency == 3
    assert settings.quality == "192"
    assert "\x00" not in settings.folder


def test_corrupt_json_is_not_overwritten_while_loading(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")
    store = JsonSettingsRepository(path)
    assert store.load() == AppSettings()
    assert path.read_text(encoding="utf-8") == "{broken"


def test_failed_save_keeps_previous_json_and_removes_temporary_file(tmp_path):
    path = tmp_path / "settings.json"
    store = JsonSettingsRepository(path)
    store.save(AppSettings(volume=0.3))
    before = path.read_bytes()
    with pytest.raises(TypeError):
        store.save(AppSettings(extra={"not_json": object()}))
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("settings-*.tmp"))

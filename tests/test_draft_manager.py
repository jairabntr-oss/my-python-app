"""
Tests para DraftManager.
"""

import json
import pytest
from core.draft_manager import DraftManager
from core.exceptions import InvalidDraftError


@pytest.fixture
def valid_draft_file(tmp_path):
    """Crea un archivo draft_content.json válido mínimo."""
    data = {
        "materials": {"texts": []},
        "tracks": [],
        "duration": 10_000_000,
    }
    draft_file = tmp_path / "draft_content.json"
    draft_file.write_text(json.dumps(data), encoding="utf-8")
    return str(draft_file)


@pytest.fixture
def invalid_json_file(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ not valid json }", encoding="utf-8")
    return str(bad_file)


@pytest.fixture
def missing_fields_file(tmp_path):
    data = {"version": "1.0"}
    f = tmp_path / "draft_content.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return str(f)


class TestDraftManagerInit:
    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            DraftManager("/ruta/inexistente/draft_content.json")

    def test_loads_valid_file(self, valid_draft_file):
        dm = DraftManager(valid_draft_file)
        assert dm.json_path.is_file()


class TestDraftManagerLoad:
    def test_load_valid_draft(self, valid_draft_file):
        dm = DraftManager(valid_draft_file)
        data = dm.load()
        assert "materials" in data
        assert "tracks" in data

    def test_load_invalid_json_raises(self, invalid_json_file):
        dm = DraftManager(invalid_json_file)
        with pytest.raises(InvalidDraftError):
            dm.load()

    def test_load_missing_fields_raises(self, missing_fields_file):
        dm = DraftManager(missing_fields_file)
        with pytest.raises(InvalidDraftError):
            dm.load()


class TestDraftManagerAnalyze:
    def test_analyze_empty_draft(self, valid_draft_file):
        dm = DraftManager(valid_draft_file)
        dm.load()
        result = dm.analyze()
        assert result["cantidad_oraciones_procesables"] == 0
        assert result["duracion_video_seg"] == pytest.approx(10.0)

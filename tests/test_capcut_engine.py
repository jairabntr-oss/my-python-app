"""
Tests de regresión para CapcutEngine.

Cubren los bugs corregidos:
- La extracción ahora delega en AutocaptionExtractor (antes parseaba una
  estructura inexistente `track["clips"][...]["startTime"]` y devolvía []).
- detect_simultaneous_dialog usa >= (consistente con SubtitleEngine).
- generate_subtitles_for_project llama al constructor correcto vía el
  factory SubtitleEngine.from_draft (antes pasaba (carpeta, nombre, perfil)
  a un constructor (script, profile)).
"""

import json
import inspect

from core.capcut_engine import CapcutEngine
from core.learning_engine import LearningEngine
from core.subtitle_engine import SubtitleEngine
from utils.extract_autocaption import AutocaptionExtractor


def _draft_minimo_con_autocaption(tmp_path):
    """draft_content.json real-ish: el auto-caption vive en
    materials.texts[].content (JSON string) con words[] en microsegundos,
    NO en track["clips"]."""
    content_words = {
        "text": "hola mundo",
        "words": [
            {"text": "hola", "start_time": 0, "end_time": 200000},
            {"text": "mundo", "start_time": 200000, "end_time": 500000},
        ],
        "texts": ["hola", "mundo"],
    }
    mat_id = "mat_caption_1"
    data = {
        "duration": 1_000_000,
        "materials": {
            "texts": [
                {"id": mat_id, "content": json.dumps(content_words)}
            ]
        },
        "tracks": [
            {
                "type": "text",
                "name": "Reconocimiento de voz",
                "segments": [{"material_id": mat_id}],
            }
        ],
    }
    proj = tmp_path / "proyecto demo"
    proj.mkdir()
    (proj / "draft_content.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    return tmp_path


def _engine_con_carpeta(carpeta) -> CapcutEngine:
    le = LearningEngine.__new__(LearningEngine)
    le.profile = le._create_default_profile()
    le.profile["capcut_paths"]["drafts_folder"] = str(carpeta)
    eng = CapcutEngine.__new__(CapcutEngine)
    eng.learning_engine = le
    eng.config = le.profile
    eng.visual_settings = le.get_visual_settings()
    eng.pycapcut_available = False
    eng.cc = None
    return eng


def test_extract_captions_delega_y_encuentra_palabras(tmp_path):
    """La extracción debe encontrar el auto-caption real (regresión: antes
    devolvía [] porque parseaba 'clips'/'startTime' inexistentes)."""
    carpeta = _draft_minimo_con_autocaption(tmp_path)
    eng = _engine_con_carpeta(carpeta)

    oraciones = eng.extract_captions_from_draft("proyecto demo")

    assert len(oraciones) == 1
    assert [p["word"] for p in oraciones[0]] == ["hola", "mundo"]
    # microsegundos preservados
    assert oraciones[0][0]["start_us"] == 0
    assert oraciones[0][1]["end_us"] == 500000


def test_extractor_unificado_coincide_con_engine(tmp_path):
    """CapcutEngine y AutocaptionExtractor deben coincidir (una sola fuente
    de verdad de parseo)."""
    carpeta = _draft_minimo_con_autocaption(tmp_path)
    eng = _engine_con_carpeta(carpeta)

    via_engine = eng.extract_captions_from_draft("proyecto demo")
    via_extractor, _ = AutocaptionExtractor.extract(
        str(carpeta / "proyecto demo" / "draft_content.json")
    )
    assert via_engine == via_extractor


def test_detect_overlap_usa_mayor_o_igual(tmp_path):
    """El umbral debe ser >= (consistente con SubtitleEngine)."""
    eng = _engine_con_carpeta(tmp_path)
    umbral = eng.visual_settings["overlap_threshold_us"]

    # overlap EXACTO al umbral -> debe contar (>=)
    oraciones = [
        [{"word": "a", "start_us": 0, "end_us": umbral}],
        [{"word": "b", "start_us": 0, "end_us": 100}],
    ]
    pares = eng.detect_simultaneous_dialog(oraciones)
    assert pares == [(0, 1)]


def test_generate_usa_factory_correcto():
    """generate_subtitles_for_project debe construir el motor con
    SubtitleEngine.from_draft, NO con el constructor (script, profile)
    pasándole strings. Verificamos que el código fuente referencia el
    factory (regresión del bug de firma)."""
    src = inspect.getsource(CapcutEngine.generate_subtitles_for_project)
    assert "SubtitleEngine.from_draft" in src
    assert "SubtitleEngine(\n" not in src  # no llamada directa al constructor


def test_from_draft_existe_y_es_classmethod():
    """El factory que usa el engine debe existir como classmethod."""
    assert isinstance(
        inspect.getattr_static(SubtitleEngine, "from_draft"), classmethod
    )

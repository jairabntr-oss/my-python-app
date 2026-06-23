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


class TestDraftManagerFormatoNuevoMaria:
    """Regresión para el caso real de 'mariaaa baic' (CapCut 8.8+):

    1. El track de auto-caption recién generado tiene name="" -> antes se
       trataba como texto MANUAL del usuario solo por el nombre vacío, sin
       mirar el contenido real, y se descartaba sin extraer nada.
    2. 'words' vive a nivel RAIZ del material (no dentro de content), como
       arrays paralelos con " " (espacio) como separador de palabras.
    3. Esos timings están en MILISEGUNDOS, no microsegundos -> sin
       convertir, los subtítulos generados durarían 1000x menos de lo real.
    """

    def _draft_formato_nuevo(self, tmp_path, con_recognize_task_id=True):
        material = {
            "id": "MAT1",
            "type": "subtitle",
            "content": json.dumps({"styles": [{"size": 30}]}),  # sin "words" adentro
            "words": {
                "start_time": [0, 240, 240, 440, 560],
                "end_time": [240, 240, 440, 440, 880],
                "text": ["vos", " ", "sos", " ", "María"],
            },
        }
        if con_recognize_task_id:
            material["recognize_task_id"] = "6a38c77c39734201f0f5f244_8_0"

        data = {
            "duration": 83_500_000,  # microsegundos reales (83.5s)
            "materials": {"texts": [material]},
            "tracks": [
                {"type": "video", "name": "", "segments": []},
                # name vacio: el caso real que se descartaba como "manual"
                {"type": "text", "name": "", "segments": [{"material_id": "MAT1"}]},
            ],
        }
        draft_file = tmp_path / "draft_content.json"
        draft_file.write_text(json.dumps(data), encoding="utf-8")
        return str(draft_file)

    def test_track_sin_nombre_no_se_descarta_como_manual(self, tmp_path):
        path = self._draft_formato_nuevo(tmp_path)
        oraciones, stats = DraftManager.oraciones_desde_json(path)

        assert stats["oraciones"] == 1, "El track con name='' se siguio tratando como manual"
        assert stats["palabras"] == 3

    def test_espacios_se_descartan_como_separador(self, tmp_path):
        path = self._draft_formato_nuevo(tmp_path)
        oraciones, _ = DraftManager.oraciones_desde_json(path)

        palabras = [p["word"] for p in oraciones[0]]
        assert palabras == ["vos", "sos", "María"]
        assert " " not in palabras

    def test_timings_se_convierten_de_milisegundos_a_microsegundos(self, tmp_path):
        path = self._draft_formato_nuevo(tmp_path)
        oraciones, _ = DraftManager.oraciones_desde_json(path)

        maria = oraciones[0][-1]
        assert maria["word"] == "María"
        # En el material real: start_time=560, end_time=880 (MILISEGUNDOS).
        # Sin la conversion, esto quedaria en 560/880 (microsegundos
        # absurdamente cortos, <1ms). Con la conversion correcta: 560000us
        # / 880000us (0.56s / 0.88s).
        assert maria["start_us"] == 560_000
        assert maria["end_us"] == 880_000

    def test_offset_del_segmento_se_suma_en_formato_nuevo(self, tmp_path):
        """Regresion: en el formato nuevo, 'words' es RELATIVO al inicio del
        SEGMENTO (target_timerange.start), no del video. Confirmado con
        datos reales de 'mariaaa baic': el segmento de 'la dueña...' tiene
        target_timerange.start=1166666us, pero su words empieza en
        start_time=0. Sin sumar ese offset, TODAS las oraciones del video
        quedaban con start_us cercano a 0 -- aplastadas unas sobre otras en
        el tiempo, lo que el motor de posicionamiento interpretaba como
        'no hay solapamiento' (porque cada bloque se procesaba como si
        ocurriera al principio del video) y producia un resultado donde el
        orden temporal real se perdia por completo."""
        material_2 = {
            "id": "MAT2",
            "type": "subtitle",
            "recognize_task_id": "otro_task_id",
            "content": json.dumps({"styles": [{"size": 30}]}),
            "words": {
                # mismos valores reales que "la dueña de todo esto no si",
                # relativos al inicio del SEGMENTO (no del video)
                "start_time": [0, 240, 560, 640, 760, 960, 1120],
                "end_time": [200, 520, 640, 760, 960, 1120, 1280],
                "text": ["la", "dueña", "de", "todo", "esto", "no", "sí"],
            },
        }
        data = {
            "duration": 83_500_000,
            "materials": {"texts": [
                {
                    "id": "MAT1",
                    "recognize_task_id": "6a38c77c39734201f0f5f244_8_0",
                    "content": json.dumps({"styles": [{"size": 30}]}),
                    "words": {
                        "start_time": [0, 240, 560],
                        "end_time": [240, 440, 880],
                        "text": ["vos", "sos", "María"],
                    },
                },
                material_2,
            ]},
            "tracks": [
                {"type": "video", "name": "", "segments": []},
                {
                    "type": "text", "name": "",
                    "segments": [
                        # offset real del primer segmento: 400000us (0.4s)
                        {"material_id": "MAT1", "target_timerange": {"start": 400000, "duration": 880000}},
                        # offset real del segundo segmento: 1166666us (1.17s)
                        {"material_id": "MAT2", "target_timerange": {"start": 1166666, "duration": 1033334}},
                    ],
                },
            ],
        }
        draft_file = tmp_path / "draft_content.json"
        draft_file.write_text(json.dumps(data), encoding="utf-8")

        oraciones, stats = DraftManager.oraciones_desde_json(str(draft_file))
        assert stats["oraciones"] == 2

        # Oracion 1 ("vos sos María"): offset 400000 + tiempos relativos
        assert oraciones[0][0]["start_us"] == 400_000  # "vos": 0 + 400000
        assert oraciones[0][-1]["end_us"] == 1_280_000  # "María": 880000 + 400000

        # Oracion 2 ("la dueña..."): offset 1166666 + tiempos relativos.
        # ANTES del fix, esto daba start_us=0 (sin offset), aplastando la
        # oracion al principio del video en vez de en su momento real (~1.17s).
        assert oraciones[1][0]["start_us"] == 1_166_666  # "la": 0 + 1166666
        # las dos oraciones ya NO empiezan ambas en (casi) el mismo punto
        assert oraciones[1][0]["start_us"] != oraciones[0][0]["start_us"]

    def test_sin_recognize_task_id_es_auto_ya_estilado_no_procesable(self, tmp_path):
        """Si el material NO tiene recognize_task_id, no es auto-caption
        nativo (podria ser texto ya editado a mano) -> no debe contarse
        como 'procesable' (oraciones_auto_sin_editar)."""
        path = self._draft_formato_nuevo(tmp_path, con_recognize_task_id=False)
        oraciones, stats = DraftManager.oraciones_desde_json(path)

        assert stats["oraciones"] == 0

    def test_formato_viejo_microsegundos_no_se_reconvierte(self, tmp_path):
        """El formato viejo (words dentro de content, ya en start_us/end_us)
        no debe pasar por el multiplicador del formato nuevo (que asumiria
        milisegundos y arruinaria timings ya correctos)."""
        content_dict = {
            "words": [
                {"text": "hola", "start_us": 0, "end_us": 200_000},
                {"text": "mundo", "start_us": 200_000, "end_us": 500_000},
            ],
            "texts": ["hola", "mundo"],
        }
        data = {
            "duration": 1_000_000,
            "materials": {"texts": [{"id": "MATV", "content": json.dumps(content_dict)}]},
            "tracks": [
                {"type": "text", "name": "Reconocimiento de voz",
                 "segments": [{"material_id": "MATV"}]},
            ],
        }
        draft_file = tmp_path / "draft_content.json"
        draft_file.write_text(json.dumps(data), encoding="utf-8")

        oraciones, _ = DraftManager.oraciones_desde_json(str(draft_file))
        assert oraciones[0][0]["end_us"] == 200_000
        assert oraciones[0][1]["end_us"] == 500_000

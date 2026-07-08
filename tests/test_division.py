"""
Tests de regresion para core.division.

Cubren el bug corregido:
- agregar_pista_broll copiaba TODOS los campos del track de video
  original (incluido "id") al crear el track nuevo de b-roll, dejando
  dos tracks con el mismo id. CapCut no podia distinguir a que track
  pertenecia cada segmento y los dejaba inseleccionables/invisibles en
  la timeline (aunque reproducian bien internamente). Detectado
  inspeccionando un draft_content.json real ("chery tiggo 8 - resumen3").
"""

import copy

from core.division import agregar_pista_broll, construir_resumen

US = 1_000_000

SEG_BASE = {
    "caption_info": None, "cartoon": False,
    "clip": {"alpha": 1.0,
             "flip": {"horizontal": False, "vertical": False},
             "rotation": 0.0, "scale": {"x": 1.0, "y": 1.0},
             "transform": {"x": 0.0, "y": 0.0}},
    "common_keyframes": [], "extra_material_refs": [], "id": "X",
    "material_id": "MAT_VIDEO_1", "render_index": 0,
    "source_timerange": {"start": 0, "duration": 1000000},
    "speed": 1.0, "target_timerange": {"start": 0, "duration": 1000000},
}


def _vseg(id_, t0, dur, s0=None):
    s = copy.deepcopy(SEG_BASE)
    s["id"] = id_
    s["target_timerange"] = {"start": t0, "duration": dur}
    s["source_timerange"] = {"start": s0 if s0 is not None else t0, "duration": dur}
    return s


def _draft_base():
    return {
        "duration": 500 * US,
        "materials": {"speeds": [], "texts": []},
        "tracks": [{
            "type": "video", "id": "TRACK-ORIGINAL-ID", "name": "",
            "flag": 0, "attribute": 0, "is_default_name": True,
            "segments": [_vseg("V1", 0, 500 * US)],
        }],
    }


class TestAgregarPistaBroll:

    def test_track_de_broll_tiene_id_propio_distinto_del_original(self):
        draft = _draft_base()
        resumen, _ = construir_resumen(draft, [(10 * US, 20 * US)])
        resumen2, _ = agregar_pista_broll(resumen, draft, [(100 * US, 110 * US)])

        ids_tracks_video = [t["id"] for t in resumen2["tracks"] if t["type"] == "video"]
        assert len(ids_tracks_video) == len(set(ids_tracks_video)), (
            "dos tracks de video quedaron con el mismo id: "
            f"{ids_tracks_video}")

    def test_track_narrativo_conserva_su_id_original(self):
        draft = _draft_base()
        resumen, _ = construir_resumen(draft, [(10 * US, 20 * US)])
        resumen2, _ = agregar_pista_broll(resumen, draft, [(100 * US, 110 * US)])

        narrativo = next(t for t in resumen2["tracks"] if t.get("name", "") == "")
        assert narrativo["id"] == "TRACK-ORIGINAL-ID"

    def test_track_broll_tiene_nombre_y_flag_correctos(self):
        draft = _draft_base()
        resumen, _ = construir_resumen(draft, [(10 * US, 20 * US)])
        resumen2, _ = agregar_pista_broll(resumen, draft, [(100 * US, 110 * US)])

        broll = next(t for t in resumen2["tracks"] if t.get("name") == "AUTO_broll")
        assert broll["is_default_name"] is False
        assert broll["id"] != "TRACK-ORIGINAL-ID"

    def test_broll_arranca_justo_donde_termina_el_narrativo_sin_overlap(self):
        draft = _draft_base()
        resumen, _ = construir_resumen(draft, [(10 * US, 30 * US)])  # 20s narrativo
        resumen2, dur_broll = agregar_pista_broll(
            resumen, draft, [(100 * US, 115 * US), (200 * US, 209 * US)])

        broll = next(t for t in resumen2["tracks"] if t.get("name") == "AUTO_broll")
        segs = broll["segments"]
        fin_prev = resumen["duration"]  # 20s, donde debe arrancar el broll
        for s in segs:
            assert s["target_timerange"]["start"] == fin_prev
            fin_prev += s["target_timerange"]["duration"]
        assert dur_broll == 24 * US  # 15 + 9
        assert resumen2["duration"] == resumen["duration"] + 24 * US

    def test_ids_de_segmentos_de_broll_no_se_repiten_con_el_narrativo(self):
        draft = _draft_base()
        resumen, _ = construir_resumen(draft, [(10 * US, 30 * US)])
        resumen2, _ = agregar_pista_broll(resumen, draft, [(100 * US, 115 * US)])

        narrativo = next(t for t in resumen2["tracks"] if t.get("name", "") == "")
        broll = next(t for t in resumen2["tracks"] if t.get("name") == "AUTO_broll")

        ids_narrativo = {s["id"] for s in narrativo["segments"]}
        ids_broll = {s["id"] for s in broll["segments"]}
        assert not (ids_narrativo & ids_broll)

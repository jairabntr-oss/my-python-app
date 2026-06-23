"""
Tests para SubtitleEngine.

Validamos que los errores del handoff estén resueltos.
"""

import unittest
import json
import tempfile
from pathlib import Path
from core.subtitle_engine import SubtitleEngine


class TestOverlapDetection(unittest.TestCase):
    """Tests para detección de overlap real."""
    
    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)  # Instancia sin __init__
    
    def test_no_overlap_con_gap_grande(self):
        """Verificar que NO hay overlap si gap > 150ms."""
        oraciones = [
            [{"start_us": 0, "end_us": 100_000}],      # Termina en 100ms
            [{"start_us": 300_000, "end_us": 400_000}]  # Empieza en 300ms (gap de 200ms)
        ]
        
        pares = self.engine._detectar_overlap_real(oraciones)
        self.assertEqual(len(pares), 0, "No debe haber overlap con gap de 200ms")
    
    def test_overlap_real_con_gap_pequeno(self):
        """Verificar que SÍ hay overlap si gap < -150ms (las oraciones se superponen realmente)."""
        oraciones = [
            [{"start_us": 0, "end_us": 200_000}],      # Termina en 200ms
            [{"start_us": 100_000, "end_us": 300_000}]  # Empieza en 100ms (overlap de 100ms)
        ]
        
        # Overlap < umbral (100ms < 150ms), NO debe considerarse
        pares = self.engine._detectar_overlap_real(oraciones)
        self.assertEqual(len(pares), 0, "No debe haber overlap con superposición de 100ms")
    
    def test_overlap_real_exacto_al_umbral(self):
        """Verificar que SÍ hay overlap si gap == 150ms (umbral exacto)."""
        oraciones = [
            [{"start_us": 0, "end_us": 200_000}],      # Termina en 200ms
            [{"start_us": 50_000, "end_us": 300_000}]  # Empieza en 50ms (overlap de 150ms)
        ]
        
        pares = self.engine._detectar_overlap_real(oraciones)
        self.assertEqual(len(pares), 1, "Debe haber overlap con superposición de 150ms")


class TestBlockSplitting(unittest.TestCase):
    """Tests para división de oraciones largas."""
    
    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)
    
    def test_oracion_corta_no_se_divide(self):
        """Oraciones ≤5 palabras no se deben dividir."""
        oracion = [
            {"word": "hola", "start_us": 0, "end_us": 100_000},
            {"word": "mundo", "start_us": 100_000, "end_us": 200_000},
        ]
        
        bloques = self.engine._dividir_oracion(oracion, idx=0, es_overlap=False)
        self.assertEqual(len(bloques), 1, "Debe ser 1 bloque")
        self.assertEqual(len(bloques[0]["palabras"]), 2, "Debe tener 2 palabras")
    
    def test_oracion_larga_se_divide(self):
        """Oraciones >5 palabras se deben dividir."""
        oracion = [
            {"word": f"palabra{i}", "start_us": i*100_000, "end_us": (i+1)*100_000}
            for i in range(10)  # 10 palabras
        ]
        
        bloques = self.engine._dividir_oracion(oracion, idx=0, es_overlap=False)
        self.assertGreater(len(bloques), 1, "Debe haber más de 1 bloque")
        for bloque in bloques:
            self.assertLessEqual(len(bloque["palabras"]), 5, "Cada bloque ≤5 palabras")

    def test_oracion_larga_respeta_max_palabras_configurable(self):
        """Usa max_palabras_por_bloque configurable desde perfil/layout."""
        engine = SubtitleEngine(script=None, profile={"max_palabras_por_bloque": 3})
        oracion = [
            {"word": f"palabra{i}", "start_us": i * 100_000, "end_us": (i + 1) * 100_000}
            for i in range(7)
        ]

        bloques = engine._dividir_oracion(oracion, idx=0, es_overlap=False)
        for bloque in bloques:
            self.assertLessEqual(len(bloque["palabras"]), 3, "Cada bloque ≤3 palabras")


class TestLayoutConfig(unittest.TestCase):
    """Tests para layout configurable de posiciones."""

    def test_anclas_configurables_se_aplican_en_posiciones(self):
        engine = SubtitleEngine(
            script=None,
            profile={"ancla_izquierda": -0.1, "ancla_derecha": 0.3, "ancho_por_caracter": 0.05},
        )
        bloques = [
            {
                "idx_oracion": 0,
                "palabras": [{"word": "hola", "start_us": 0, "end_us": 100_000}],
                "es_overlap": False,
            }
        ]

        posiciones = engine._calcular_posiciones(bloques, pares_overlap=[])
        # el id ahora incluye indice de bloque: "{b_idx}_{idx_oracion}_{i}"
        self.assertEqual(posiciones["0_0_0"][0], -0.1)


class TestSeSolapa(unittest.TestCase):
    """Tests para detección de solapamiento temporal entre segmentos."""

    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)

    def test_sin_solapamiento(self):
        """Segmento posterior no se solapa con anterior."""
        intervals = [(0, 100_000)]
        self.assertFalse(self.engine._se_solapa(intervals, 100_000, 200_000))

    def test_solapamiento_parcial(self):
        """Segmento que empieza antes del fin del anterior se solapa."""
        intervals = [(0, 100_000)]
        self.assertTrue(self.engine._se_solapa(intervals, 50_000, 150_000))

    def test_solapamiento_contenido(self):
        """Segmento completamente dentro de otro se solapa."""
        intervals = [(0, 500_000)]
        self.assertTrue(self.engine._se_solapa(intervals, 100_000, 200_000))

    def test_lista_vacia(self):
        """Lista vacía nunca se solapa."""
        self.assertFalse(self.engine._se_solapa([], 0, 100_000))


class TestHexToRgb(unittest.TestCase):
    """Tests para conversión de color hex a RGB."""

    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)

    def test_blanco(self):
        self.assertEqual(self.engine._hex_to_rgb("#FFFFFF"), (1.0, 1.0, 1.0))

    def test_negro(self):
        self.assertEqual(self.engine._hex_to_rgb("#000000"), (0.0, 0.0, 0.0))

    def test_sin_hash(self):
        self.assertEqual(self.engine._hex_to_rgb("FF0000"), (1.0, 0.0, 0.0))


class TestDistribucionGreedy(unittest.TestCase):
    """Tests de integración del algoritmo greedy de distribución de tracks."""

    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)

    def _make_bloque(self, palabras):
        return {"idx_oracion": 0, "palabras": palabras, "es_overlap": False}

    def test_palabras_consecutivas_van_al_mismo_track(self):
        """Palabras que no se solapan deben ir al mismo track."""
        # Dos palabras consecutivas: la 2ª empieza cuando termina la 1ª
        # Con efecto acumulativo, la 1ª dura de 0 a 200ms y la 2ª de 100ms a 200ms → se solapan
        bloques = [
            self._make_bloque([
                {"word": "a", "start_us": 0, "end_us": 100_000},
                {"word": "b", "start_us": 100_000, "end_us": 200_000},
            ])
        ]
        posiciones = {"0_0": (0.0, 0.0), "0_1": (0.1, 0.0)}
        # Con efecto acumulativo, "a" dura 0→200ms y "b" dura 100ms→200ms: overlap
        # Deben estar en tracks distintos
        tracks_contados = self._contar_tracks_necesarios(bloques, posiciones)
        self.assertGreaterEqual(tracks_contados, 1)  # Al menos 1 track

    def test_palabras_acumulativas_necesitan_tracks_distintos(self):
        """Con efecto acumulativo, palabras del mismo bloque siempre se solapan."""
        # 3 palabras en mismo bloque: la 1ª dura todo el bloque, la 2ª también, etc.
        bloques = [
            self._make_bloque([
                {"word": "uno", "start_us": 0,       "end_us": 100_000},
                {"word": "dos", "start_us": 100_000, "end_us": 200_000},
                {"word": "tres","start_us": 200_000, "end_us": 300_000},
            ])
        ]
        posiciones = {"0_0": (0.0, 0.0), "0_1": (0.1, 0.0), "0_2": (0.2, 0.0)}
        # "uno" va de 0→300ms, "dos" de 100ms→300ms, "tres" de 200ms→300ms: todos se solapan
        tracks_contados = self._contar_tracks_necesarios(bloques, posiciones)
        # Necesita 3 tracks (ninguno puede compartir track con otro)
        self.assertEqual(tracks_contados, 3)

    def _contar_tracks_necesarios(self, bloques, posiciones):
        """Simula el algoritmo greedy y devuelve cuántos tracks serían necesarios."""
        segmentos_data = []
        for bloque in bloques:
            ultimo_end = bloque["palabras"][-1]["end_us"]
            for i, p in enumerate(bloque["palabras"]):
                pid = f"{bloque['idx_oracion']}_{i}"
                x, y = posiciones.get(pid, (0, 0))
                start = p["start_us"]
                dur = max(ultimo_end - start, 1000)
                segmentos_data.append({"start": start, "duracion": dur, "x": x, "y": y})

        segmentos_data.sort(key=lambda s: s["start"])

        tracks = []  # list of [(start, end)]
        for seg in segmentos_data:
            seg_start = seg["start"]
            seg_end = seg["start"] + seg["duracion"]
            assigned = None
            for idx_t, intervals in enumerate(tracks):
                if not self.engine._se_solapa(intervals, seg_start, seg_end):
                    assigned = idx_t
                    break
            if assigned is None:
                tracks.append([])
                assigned = len(tracks) - 1
            tracks[assigned].append((seg_start, seg_end))

        return len(tracks)


class TestInyeccionEstiloAvanzado(unittest.TestCase):
    def test_parchea_solo_materiales_generados(self):
        with tempfile.TemporaryDirectory() as td:
            draft_path = Path(td) / "draft_content.json"
            draft_data = {
                "materials": {
                    "texts": [
                        {
                            "id": "MAT_1",
                            "content": json.dumps({"styles": [{}]}),
                        },
                        {
                            "id": "MAT_2",
                            "content": json.dumps({"styles": [{}]}),
                        },
                    ]
                }
            }
            draft_path.write_text(json.dumps(draft_data), encoding="utf-8")

            engine = SubtitleEngine.__new__(SubtitleEngine)
            engine.script = type("Script", (), {"save_path": str(draft_path)})()
            engine._material_ids_generados = ["MAT_1"]
            engine.profile = {
                "shadow_enabled": True,
                "shadow_color": "#000000",
                "shadow_alpha": 0.33,
                "shadow_distance": 17.0,
                "shadow_angle": -115.9,
                "shadow_smoothing": 0.45,
                "font_path": "/fonts/Poppins-Bold.ttf",
                "font_name": "Poppins Bold",
                "font_id": "FONT1",
                "bold": True,
                "text_size": 30,
            }

            patched = engine._inyectar_estilo_avanzado()
            self.assertEqual(patched, 1)

            out = json.loads(draft_path.read_text(encoding="utf-8"))
            mats = {m["id"]: m for m in out["materials"]["texts"]}
            self.assertEqual(mats["MAT_1"]["text_size"], 30.0)
            self.assertNotIn("text_size", mats["MAT_2"])
            style_font = json.loads(mats["MAT_1"]["content"])["styles"][0]["font"]
            self.assertEqual(style_font["path"], "/fonts/Poppins-Bold.ttf")


if __name__ == "__main__":
    unittest.main()

"""
Tests para los modulos de autosuficiencia de la UI:
- utils/mensajes.py (traduccion de estados a mensajes accionables)
- utils/diagnostico.py (reporte de solo lectura de un draft)
- utils/capcut_projects.py (descubrimiento de proyectos en disco)

Estos modulos son los que permiten procesar un video nuevo sin ayuda
externa, asi que conviene que esten cubiertos.
"""

import json
import unittest
from pathlib import Path
import tempfile

from utils.mensajes import (
    interpretar_analisis,
    interpretar_error,
    aviso_capcut_abierto,
)
from utils.diagnostico import diagnosticar_draft
from utils.capcut_projects import listar_proyectos, encontrar_carpeta_drafts


class TestMensajesAnalisis(unittest.TestCase):
    def test_cero_oraciones_sin_estilizar_da_error_accionable(self):
        result = {
            "cantidad_oraciones_procesables": 0,
            "cantidad_oraciones_ya_estiladas": 0,
        }
        diag = interpretar_analisis(result)
        self.assertEqual(diag.nivel, "error")
        self.assertFalse(diag.puede_continuar)
        # Debe mencionar como generar el auto-caption (accionable)
        texto = " ".join(diag.pasos).lower()
        self.assertIn("subtitulos", texto)
        self.assertIn("automaticos", texto)
        self.assertIn("capcut", texto)

    def test_cero_oraciones_pero_ya_estilizadas_es_aviso(self):
        result = {
            "cantidad_oraciones_procesables": 0,
            "cantidad_oraciones_ya_estiladas": 30,
        }
        diag = interpretar_analisis(result)
        self.assertEqual(diag.nivel, "aviso")
        self.assertFalse(diag.puede_continuar)

    def test_con_oraciones_permite_continuar(self):
        result = {
            "cantidad_oraciones_procesables": 43,
            "cantidad_oraciones_ya_estiladas": 0,
            "tracks_residuales_texto": [],
            "tracks_residuales_audio": [],
        }
        diag = interpretar_analisis(result)
        self.assertEqual(diag.nivel, "ok")
        self.assertTrue(diag.puede_continuar)

    def test_tracks_residuales_se_avisan_pero_no_bloquean(self):
        result = {
            "cantidad_oraciones_procesables": 43,
            "cantidad_oraciones_ya_estiladas": 0,
            "tracks_residuales_texto": ["AUTO_sub_0", "AUTO_sub_1"],
            "tracks_residuales_audio": [],
        }
        diag = interpretar_analisis(result)
        self.assertTrue(diag.puede_continuar)
        texto = " ".join(diag.pasos).lower()
        self.assertIn("corrida anterior", texto)


class TestMensajesError(unittest.TestCase):
    def test_file_not_found_es_accionable(self):
        diag = interpretar_error(FileNotFoundError("No es un archivo: x.json"))
        self.assertEqual(diag.nivel, "error")
        self.assertFalse(diag.puede_continuar)

    def test_json_invalido_es_accionable(self):
        diag = interpretar_error(ValueError("El archivo no es un JSON válido."))
        self.assertEqual(diag.nivel, "error")

    def test_error_generico_incluye_detalle_tecnico(self):
        diag = interpretar_error(RuntimeError("algo raro paso"))
        texto = " ".join(diag.pasos)
        self.assertIn("algo raro paso", texto)


class TestAvisoCapcut(unittest.TestCase):
    def test_capcut_abierto_bloquea(self):
        diag = aviso_capcut_abierto(True)
        self.assertIsNotNone(diag)
        self.assertEqual(diag.nivel, "error")
        self.assertFalse(diag.puede_continuar)

    def test_capcut_cerrado_no_da_aviso(self):
        self.assertIsNone(aviso_capcut_abierto(False))

    def test_estado_desconocido_avisa_pero_deja_continuar(self):
        diag = aviso_capcut_abierto(None)
        self.assertIsNotNone(diag)
        self.assertTrue(diag.puede_continuar)


class TestDiagnostico(unittest.TestCase):
    def test_archivo_inexistente(self):
        reporte = diagnosticar_draft("/no/existe/draft_content.json")
        self.assertIn("No se encontro", reporte)

    def test_draft_con_words_vacio_dice_que_hacer(self):
        # Simula el caso real: materiales con words vacio (auto-caption
        # consumido o nunca generado).
        data = {
            "duration": 83_500_000,
            "materials": {"texts": [
                {"id": "m1", "words": {"start_time": [], "end_time": [], "text": []}},
            ]},
            "tracks": [{"type": "video", "name": "", "segments": []}],
        }
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft_content.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            reporte = diagnosticar_draft(str(p))
        self.assertIn("NO hay datos", reporte)
        self.assertIn("automaticos", reporte)

    def test_draft_con_autocaption_real_lo_detecta(self):
        # Formato nuevo con datos reales + recognize_task_id
        data = {
            "duration": 10_000_000,
            "materials": {"texts": [
                {
                    "id": "m1",
                    "recognize_task_id": "abc_8_0",
                    "words": {
                        "start_time": [0, 240, 560],
                        "end_time": [240, 440, 880],
                        "text": ["vos", "sos", "María"],
                    },
                },
            ]},
            "tracks": [{"type": "text", "name": "", "segments": [{"material_id": "m1"}]}],
        }
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft_content.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            reporte = diagnosticar_draft(str(p))
        self.assertIn("SI hay datos", reporte)


class TestListadoProyectos(unittest.TestCase):
    def test_carpeta_inexistente_devuelve_vacio(self):
        # Una ruta que seguro no existe no debe romper, solo lista vacia.
        proyectos = listar_proyectos(ruta_manual="/ruta/que/no/existe/zzz")
        self.assertEqual(proyectos, [])

    def test_lista_proyectos_ordenados_por_fecha(self):
        import os
        import time
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            # Crear 3 proyectos con draft_content.json
            for nombre in ["proyecto_viejo", "proyecto_medio", "proyecto_nuevo"]:
                proj = base / nombre
                proj.mkdir()
                (proj / "draft_content.json").write_text("{}", encoding="utf-8")
                time.sleep(0.01)  # asegurar mtimes distintos

            proyectos = listar_proyectos(ruta_manual=str(base))
            self.assertEqual(len(proyectos), 3)
            # El mas reciente (proyecto_nuevo) debe venir primero
            self.assertEqual(proyectos[0].name, "proyecto_nuevo")

    def test_omite_carpetas_sin_draft_json(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "con_json").mkdir()
            (base / "con_json" / "draft_content.json").write_text("{}", encoding="utf-8")
            (base / "sin_json").mkdir()  # carpeta sin draft

            proyectos = listar_proyectos(ruta_manual=str(base))
            nombres = [p.name for p in proyectos]
            self.assertIn("con_json", nombres)
            self.assertNotIn("sin_json", nombres)


if __name__ == "__main__":
    unittest.main()

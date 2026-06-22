"""
Tests de regresión para _calcular_posiciones (bug de María: posiciones
amontonadas / palabras cortadas).

Causa raíz que estos tests fijan:
1. ancho_palabra estaba en otra escala que las anclas (±0.20) -> el clamp de
   X se invertía para cualquier palabra de 7+ letras, y max(lo, min(hi, x))
   con lo > hi devolvía SIEMPRE lo mismo (lo), sin importar i%2 (izquierda/
   derecha). Resultado real: todas las palabras largas de un video quedaban
   exactamente en el mismo punto X.
2. El clamp final de Y aplastaba contra y_zona_max cualquier palabra que el
   anti-colisión hubiera movido fuera de la zona "blanda", lo cual también
   amontonaba varias palabras en la misma Y cuando un bloque era denso.
"""

import unittest

from core.subtitle_engine import SubtitleEngine


def _engine():
    return SubtitleEngine.__new__(SubtitleEngine)


class TestPalabrasLargasNoColapsanEnElMismoPunto(unittest.TestCase):
    """Antes del fix: 'camioneta', 'tecnologia', etc. terminaban todas en el
    mismo x porque el clamp se invertía. Ahora deben conservar la alternancia
    izquierda/derecha (o al menos no ser todas idénticas)."""

    def setUp(self):
        self.engine = _engine()
        self.engine.max_palabras_por_bloque = 5
        self.engine.ancla_izquierda = -0.20
        self.engine.ancla_derecha = 0.20
        self.engine.ancho_por_caracter = 0.15

    def test_palabras_largas_alternadas_no_son_todas_iguales(self):
        # Una sola oración con varias palabras largas (>=8 letras), que es
        # justo el caso que colapsaba antes del fix.
        oracion = [
            {"word": "camioneta", "start_us": 0, "end_us": 300_000},
            {"word": "tecnologia", "start_us": 300_000, "end_us": 600_000},
            {"word": "recomiendo", "start_us": 600_000, "end_us": 900_000},
        ]
        bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
        posiciones = self.engine._calcular_posiciones(bloques, [])

        xs = [posiciones[f"0_0_{i}"][0] for i in range(len(oracion))]
        # No deben ser TODAS exactamente el mismo valor (el bug original).
        self.assertNotEqual(
            len(set(xs)), 1,
            f"Todas las palabras largas cayeron en el mismo X: {xs}",
        )

    def test_clamp_de_x_nunca_se_invierte_con_palabra_muy_larga(self):
        """Con una palabra absurdamente larga, el código no debe reventar ni
        devolver un valor fuera de [-0.45, 0.45]; debe caer a 0.0 (centro)."""
        oracion = [
            {"word": "x" * 30, "start_us": 0, "end_us": 300_000},
        ]
        bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
        posiciones = self.engine._calcular_posiciones(bloques, [])
        x, _y = posiciones["0_0_0"]
        self.assertEqual(x, 0.0)


class TestBloqueDensoNoAplastaTodoEnLaMismaY(unittest.TestCase):
    """Antes del fix: si el anti-colisión empujaba una palabra fuera de la
    zona "blanda", el clamp final la aplastaba de vuelta a y_zona_max, y
    varias palabras consecutivas podían terminar en EXACTAMENTE el mismo Y.
    """

    def setUp(self):
        self.engine = _engine()
        self.engine.max_palabras_por_bloque = 5
        self.engine.ancla_izquierda = -0.20
        self.engine.ancla_derecha = 0.20
        self.engine.ancho_por_caracter = 0.15

    def test_bloque_de_5_palabras_cortas_no_colapsa_en_un_solo_y(self):
        # 5 palabras cortas muy seguidas en el tiempo (bloque máximo
        # permitido), el caso más exigente para el anti-colisión.
        oracion = [
            {"word": "que", "start_us": i * 50_000, "end_us": i * 50_000 + 40_000}
            for i in range(5)
        ]
        bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
        posiciones = self.engine._calcular_posiciones(bloques, [])

        ys = [round(posiciones[f"0_0_{i}"][1], 4) for i in range(len(oracion))]
        self.assertGreater(
            len(set(ys)), 1,
            f"Las 5 palabras del bloque cayeron todas en el mismo Y: {ys}",
        )


if __name__ == "__main__":
    unittest.main()

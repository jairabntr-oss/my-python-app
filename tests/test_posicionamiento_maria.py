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


class TestNoHayDosPalabrasSimultaneasEnLaMismaPosicion(unittest.TestCase):
    """Regresión del caso real de 'mariaaa baic': 'vos sos María' (oración 1)
    y 'la dueña de todo esto' (oración 2) se solapan en el tiempo.

    NOTA sobre la causa real: al inspeccionar el draft real, las palabras
    simultáneas NO estaban en posición idéntica: estaban a 0.05 en Y dentro
    de la misma columna (el espaciado normal de línea del estilo karaoke).
    El amontonamiento visible lo causaba el TEXTO 3x mas grande de lo
    calibrado (style.size=30 en vez de 10), no las posiciones. Con
    style.size=10 ese espaciado de 0.05 es correcto y legible.

    Este test verifica el invariante que SI debe cumplirse siempre: dos
    palabras visibles a la vez nunca deben caer en EL MISMO punto (mismo X
    y mismo Y), que era el sintoma del bug de colision real."""

    def setUp(self):
        self.engine = _engine()
        self.engine.max_palabras_por_bloque = 5
        self.engine.ancla_izquierda = -0.20
        self.engine.ancla_derecha = 0.20
        self.engine.ancho_por_caracter = 0.15

    def test_oraciones_solapadas_no_comparten_posicion(self):
        oracion1 = [
            {"word": "vos", "start_us": 400000, "end_us": 670000},
            {"word": "sos", "start_us": 670000, "end_us": 970000},
            {"word": "María", "start_us": 970000, "end_us": 1300000},
        ]
        oracion2 = [
            {"word": "la", "start_us": 1170000, "end_us": 1430000},
            {"word": "dueña", "start_us": 1430000, "end_us": 1730000},
            {"word": "de", "start_us": 1730000, "end_us": 1830000},
            {"word": "todo", "start_us": 1830000, "end_us": 1930000},
            {"word": "esto", "start_us": 1930000, "end_us": 2130000},
        ]
        bloques = [
            {"idx_oracion": 0, "palabras": oracion1, "es_overlap": False},
            {"idx_oracion": 1, "palabras": oracion2, "es_overlap": False},
        ]
        posiciones = self.engine._calcular_posiciones(bloques, [])

        # Ninguna palabra de la oración 2 (visible junto con la 1) debe caer
        # en EL MISMO punto que una palabra de la oración 1. Umbral 0.03:
        # por debajo del espaciado normal de linea (0.05) y del min_dist_y
        # (0.04), asi que solo detecta superposicion real (mismo punto), no
        # el apilado normal del estilo karaoke.
        pos_o1 = [posiciones[f"0_0_{i}"] for i in range(3)]
        for j in range(5):
            x2, y2 = posiciones[f"1_1_{j}"]
            for (x1, y1) in pos_o1:
                mismo_punto = abs(x1 - x2) < 0.03 and abs(y1 - y2) < 0.03
                self.assertFalse(
                    mismo_punto,
                    f"Palabra de oración 2 en ({x2:.2f},{y2:.2f}) cae en el "
                    f"mismo punto que una de oración 1 en ({x1:.2f},{y1:.2f})",
                )

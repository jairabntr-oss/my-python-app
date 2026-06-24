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
        # Una sola oración con varias palabras largas (>=8 letras).
        #
        # NOTA: con el fix de "radio seguro" (ver _calcular_posiciones), las
        # palabras largas ahora se CENTRAN a propósito en x=0 -- es
        # intencional, no el bug original. Centrarlas evita que invadan la
        # columna opuesta en diálogo simultáneo (confirmado con un caso
        # real: "reservamos" sin centrar invadía la columna en -0.20).
        # Lo que sigue siendo un invariante real es que, al compartir todas
        # la misma columna X, deben separarse en Y para no apilarse.
        oracion = [
            {"word": "camioneta", "start_us": 0, "end_us": 300_000},
            {"word": "tecnologia", "start_us": 300_000, "end_us": 600_000},
            {"word": "recomiendo", "start_us": 600_000, "end_us": 900_000},
        ]
        bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
        posiciones = self.engine._calcular_posiciones(bloques, [])

        ys = [round(posiciones[f"0_0_{i}"][1], 4) for i in range(len(oracion))]
        self.assertEqual(
            len(set(ys)), len(oracion),
            f"Palabras largas en la misma columna deben separarse en Y: {ys}",
        )

    def test_clamp_de_x_nunca_se_invierte_con_palabra_muy_larga(self):
        """Con una palabra absurdamente larga, el código no debe reventar ni
        devolver un valor fuera de [-0.45, 0.45]. Con el factor de reduccion
        dinamico (ver _calcular_posiciones), una palabra muy larga se achica
        lo suficiente para entrar en rango en vez de requerir el caso
        especial de "centrar en 0"; lo que importa es que el resultado
        siempre quede dentro de pantalla y con un factor de reduccion < 1."""
        oracion = [
            {"word": "x" * 30, "start_us": 0, "end_us": 300_000},
        ]
        bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
        posiciones = self.engine._calcular_posiciones(bloques, [])
        x, _y, factor = posiciones["0_0_0"]
        self.assertGreaterEqual(x, -0.45)
        self.assertLessEqual(x, 0.45)
        self.assertLess(factor, 1.0, "una palabra de 30 letras debe reducirse")


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
        pos_o1 = [(posiciones[f"0_0_{i}"][0], posiciones[f"0_0_{i}"][1]) for i in range(3)]
        for j in range(5):
            x2, y2, _factor2 = posiciones[f"1_1_{j}"]
            for (x1, y1) in pos_o1:
                mismo_punto = abs(x1 - x2) < 0.03 and abs(y1 - y2) < 0.03
                self.assertFalse(
                    mismo_punto,
                    f"Palabra de oración 2 en ({x2:.2f},{y2:.2f}) cae en el "
                    f"mismo punto que una de oración 1 en ({x1:.2f},{y1:.2f})",
                )


class TestPalabraLargaNoInvadeColumnaOpuestaEnOverlap(unittest.TestCase):
    """Regresión del caso real visto en captura de 'mariaaa baic':
    'reservamos' (10 letras) simultánea con 'lo que te' (oración de
    diálogo cruzado) quedaba tapando ambas columnas (-0.20 y +0.20),
    haciendo el texto ilegible. Confirmado matemáticamente: sin reducción,
    'reservamos' con ancho_por_caracter=0.15 mide 0.75 de radio, mas ancho
    que TODA la pantalla visible (-0.45 a 0.45)."""

    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)
        self.engine.max_palabras_por_bloque = 5
        self.engine.ancla_izquierda = -0.20
        self.engine.ancla_derecha = 0.20
        self.engine.ancho_por_caracter = 0.15

    def test_reservamos_se_reduce_pero_respeta_piso_minimo_de_legibilidad(self):
        """Pedido explícito del usuario (tras ver 'encontráselo' reducida a
        un tamaño casi ilegible): nunca reducir una palabra larga por debajo
        de PISO_FACTOR_REDUCCION (0.7), aunque eso signifique que palabras
        MUY largas (10+ letras como "reservamos") puedan volver a invadir
        la columna opuesta en diálogo simultáneo. Es un trade-off consciente
        elegido por el usuario: legibilidad de la palabra individual por
        sobre evitar el solape total en el peor caso. Este test verifica el
        piso, no la ausencia de invasión (eso ya no se garantiza al 100%
        para palabras de 10+ letras con el piso activo)."""
        oracion1 = [{"word": "reservamos", "start_us": 45033333, "end_us": 45700000}]
        oracion2 = [
            {"word": "lo", "start_us": 44900000, "end_us": 45100000},
            {"word": "que", "start_us": 44766666, "end_us": 44966666},
            {"word": "sí", "start_us": 44933333, "end_us": 45133333},
            {"word": "te", "start_us": 44833333, "end_us": 45033333},
        ]
        bloques = [
            {"idx_oracion": 0, "palabras": oracion1, "es_overlap": False},
            {"idx_oracion": 1, "palabras": oracion2, "es_overlap": False},
        ]
        posiciones = self.engine._calcular_posiciones(bloques, [])
        x, _y, factor = posiciones["0_0_0"]

        # El piso es 0.7 -- nunca debe reducirse mas alla de eso.
        self.assertGreaterEqual(factor, 0.7)
        # Sigue centrada en 0 (no se mueve a un lado u otro).
        self.assertEqual(x, 0.0)


class TestAlineadoPorBordeIzquierdo(unittest.TestCase):
    """Pedido del usuario tras ver su estilo manual de referencia (imagen
    real: "de" / "7 años" en lineas consecutivas de la misma columna no
    compartian el mismo eje vertical -> se veian "torcidas"). Ahora las
    palabras de una misma columna deben compartir el mismo BORDE IZQUIERDO
    (columna par) o BORDE DERECHO (columna impar), no el mismo centro fijo.
    """

    def setUp(self):
        self.engine = SubtitleEngine.__new__(SubtitleEngine)
        self.engine.max_palabras_por_bloque = 5
        self.engine.ancla_izquierda = -0.20
        self.engine.ancla_derecha = 0.20
        self.engine.ancho_por_caracter = 0.15

    def test_palabras_cortas_no_se_amontonan_cerca_del_centro(self):
        """Regresión de un bug introducido por una primera implementación
        de "alineado por borde": usar el ancho COMPLETO de la palabra como
        offset (x = borde + ancho_palabra) hacía que el centro se disparara
        según el largo real -- una palabra de 3 letras ya desplazaba el
        centro 0.225, MAS que la distancia del borde al centro de pantalla
        (0.20), cruzando al lado opuesto. Confirmado con datos reales: "que"
        terminaba en x=+0.025 en vez de cerca de la columna -0.20, y la
        mayoría de las palabras cortas del video real quedaban amontonadas
        entre ±0.10 del centro en vez de repartidas en las dos columnas
        (visible en captura real: "voy", "listo", "que" superpuestas).

        El fix usa un offset chico y ACOTADO (no proporcional al ancho
        completo), así que palabras de cualquier longitud corta/media deben
        quedar razonablemente cerca de su ancla (no amontonadas en ±0.10)."""
        for palabra in ["que", "voy", "listo", "no", "por"]:
            oracion = [{"word": palabra, "start_us": 0, "end_us": 100_000}]
            bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
            posiciones = self.engine._calcular_posiciones(bloques, [])
            x, _y, _factor = posiciones["0_0_0"]
            # ancla_izquierda=-0.20; el resultado debe quedar razonablemente
            # cerca de la columna, no amontonado en el 50% central de la
            # pantalla (-0.10 a +0.10).
            self.assertLess(
                x, -0.10,
                f"'{palabra}' en x={x:.3f}, demasiado cerca del centro (columna esperada cerca de -0.20)",
            )

    def test_palabras_de_distinto_largo_en_misma_columna_quedan_cerca(self):
        # "de" (2 letras, corta) y una palabra mas larga en la misma
        # columna (ambas en posicion par, i=0 y i=2) deben quedar
        # razonablemente cerca entre si -- no es alineado de borde EXACTO
        # (eso causaba el bug de amontonamiento, ver test de arriba), pero
        # tampoco deben volver a estar tan lejos como con centro fijo puro.
        oracion = [
            {"word": "de", "start_us": 0, "end_us": 100_000},
            {"word": "siete", "start_us": 100_000, "end_us": 200_000},
            {"word": "anios", "start_us": 200_000, "end_us": 300_000},
        ]
        bloques = [{"idx_oracion": 0, "palabras": oracion, "es_overlap": False}]
        posiciones = self.engine._calcular_posiciones(bloques, [])

        x_de, _, _ = posiciones["0_0_0"]
        x_anios, _, _ = posiciones["0_0_2"]

        # Con el offset acotado (max 0.08), ambas caen en el mismo punto
        # cuando el ancho_palabra de ambas supera la referencia de 3 letras.
        self.assertAlmostEqual(x_de, x_anios, places=4)

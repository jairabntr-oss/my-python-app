"""
Tests para SubtitleEngine.

Validamos que los errores del handoff estén resueltos.
"""

import unittest
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


if __name__ == "__main__":
    unittest.main()

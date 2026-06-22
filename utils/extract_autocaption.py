"""
Extrae las oraciones del auto-caption de un draft de CapCut v167+.

La estructura que buscamos está en materials.texts[].words con:
- start_time: array de timings en milisegundos
- end_time: array de timings en milisegundos  
- text: array de palabras (incluyendo espacios)
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple


class AutocaptionExtractor:
    """Extrae auto-caption del draft de CapCut v167+."""
    
    @staticmethod
    def extract(json_path: str) -> Tuple[List[List[Dict]], Dict]:
        """Extrae oraciones con palabras y timings.
        
        Returns:
            (oraciones, stats)
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                draft = json.load(f)
        except Exception as e:
            return [], {"error": f"Error leyendo JSON: {e}"}
        
        oraciones = []
        stats = {
            "total_materials": 0,
            "materiales_con_words": 0,
            "oraciones_extraidas": 0
        }
        
        # Obtener materiales de texto
        materials_texts = draft.get('materials', {}).get('texts', [])
        stats["total_materials"] = len(materials_texts)
        
        # Procesar cada material de texto
        for material in materials_texts:
            # Verificar que tenga campo 'words'
            words_data = material.get('words', {})
            if not words_data:
                continue
            
            stats["materiales_con_words"] += 1
            
            # Extraer palabras con timings
            oracion = AutocaptionExtractor._extraer_oracion(words_data)
            
            if oracion:
                oraciones.append(oracion)
                stats["oraciones_extraidas"] += 1
        
        return oraciones, stats
    
    @staticmethod
    def _extraer_oracion(words_data: Dict) -> List[Dict]:
        """Extrae una oración individual con palabras y timings.
        
        En CapCut v167, los timings están en milisegundos.
        Retorna oraciones en microsegundos (multiplicando por 1000).
        """
        
        text_list = words_data.get('text', [])
        start_times_ms = words_data.get('start_time', [])
        end_times_ms = words_data.get('end_time', [])
        
        if not text_list or not start_times_ms:
            return []
        
        oracion = []
        
        for i, palabra_raw in enumerate(text_list):
            # Limpiar palabra
            palabra = palabra_raw.strip()
            
            # Ignorar espacios puros
            if not palabra or palabra == " ":
                continue
            
            # Obtener timings en milisegundos
            start_ms = start_times_ms[i] if i < len(start_times_ms) else 0
            end_ms = end_times_ms[i] if i < len(end_times_ms) else 0
            
            # Convertir a microsegundos
            start_us = int(start_ms * 1000)
            end_us = int(end_ms * 1000)
            
            # Si el timing es 0, usar duración estimada
            if end_us <= start_us:
                end_us = start_us + 100_000  # 100ms estimado
            
            oracion.append({
                "word": palabra,
                "start_us": start_us,
                "end_us": end_us
            })
        
        return oracion


def main():
    """Script principal."""
    if len(sys.argv) < 2:
        print("Uso: python utils/extract_autocaption.py <ruta_json>")
        print("  Ejemplo: python utils/extract_autocaption.py C:\\\\Users\\\\user2\\\\Desktop\\\\draft_arrizzo8.json")
        sys.exit(1)
    
    json_path = sys.argv[1]
    
    if not Path(json_path).exists():
        print(f"❌ Error: No se encontró el archivo {json_path}")
        sys.exit(1)
    
    print(f"\n🔍 Extrayendo auto-caption de: {json_path}\n")
    
    oraciones, stats = AutocaptionExtractor.extract(json_path)
    
    if "error" in stats:
        print(f"❌ {stats['error']}")
        sys.exit(1)
    
    # Mostrar estadísticas
    print(f"📊 Estadísticas:")
    print(f"  - Materiales de texto totales: {stats['total_materials']}")
    print(f"  - Materiales con 'words': {stats['materiales_con_words']}")
    print(f"  - Oraciones extraídas: {stats['oraciones_extraidas']}")
    total_palabras = sum(len(o) for o in oraciones)
    print(f"  - Total de palabras: {total_palabras}")
    
    # Guardar resultado
    output_path = Path(json_path).parent / 'oraciones_autocaption.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(oraciones, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Guardado en: {output_path}")
    
    # Mostrar preview
    if oraciones:
        print(f"\n📝 Preview - Primeras 5 oraciones:")
        for i, oracion in enumerate(oraciones[:5]):
            palabras = [p['word'] for p in oracion]
            tiempo_inicio = oracion[0]['start_us'] / 1e6 if oracion else 0
            tiempo_fin = oracion[-1]['end_us'] / 1e6 if oracion else 0
            print(f"  {i+1}. [{tiempo_inicio:.2f}s - {tiempo_fin:.2f}s] {' '.join(palabras)}")
    else:
        print(f"\n⚠️  No se encontraron oraciones en el JSON")
    
    print(f"\n💡 Próximos pasos:")
    print(f"   1. Verifica las oraciones en: {output_path}")
    print(f"   2. Cierra CapCut completamente")
    print(f"   3. Ejecuta: python run_generation.py '{output_path}' 'arrizzo 8'")


if __name__ == '__main__':
    main()

"""
Extrae las oraciones del auto-caption sin editar de un draft de CapCut.

El criterio es: si el texto reconstruido desde el campo 'words' coincide exactamente 
con el texto del segmento, es auto-caption sin editar (no fue modificado manualmente).
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple


class AutocaptionExtractor:
    """Extrae auto-caption sin editar del draft de CapCut v167+."""
    
    @staticmethod
    def extract(json_path: str) -> Tuple[List[List[Dict]], Dict]:
        """Extrae oraciones de auto-caption sin editar.
        
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
            "total_tracks": 0,
            "tracks_texto": 0,
            "segments": 0,
            "oraciones_validas": 0,
            "detalles": []
        }
        
        # Obtener lista de materiales de texto
        materials_texts = draft.get('materials', {}).get('texts', [])
        material_dict = {m.get('id'): m for m in materials_texts}
        
        # Buscar en todos los tracks
        for track_idx, track in enumerate(draft.get('tracks', [])):
            stats["total_tracks"] += 1
            
            # Solo procesar tracks de texto
            if track.get('type') != 'text':
                continue
            
            stats["tracks_texto"] += 1
            track_name = track.get('extra', {}).get('track_name', f'Track {track_idx}')
            
            # Procesar segmentos del track
            for seg_idx, segment in enumerate(track.get('segments', [])):
                stats["segments"] += 1
                
                material_id = segment.get('material_id')
                if not material_id:
                    continue
                
                material = material_dict.get(material_id)
                if not material:
                    continue
                
                # Extraer palabras con timings
                oracion = AutocaptionExtractor._extraer_palabras_del_material(
                    material, segment
                )
                
                if oracion:
                    oraciones.append(oracion)
                    stats["oraciones_validas"] += 1
                    stats["detalles"].append({
                        "track": track_name,
                        "segment": seg_idx,
                        "palabras": len(oracion),
                        "texto": " ".join(p["word"] for p in oracion)
                    })
        
        return oraciones, stats
    
    @staticmethod
    def _extraer_palabras_del_material(material: Dict, segment: Dict) -> List[Dict]:
        """Extrae palabras con timings exactos de un material de texto."""
        
        # Buscar datos de palabras
        words_data = material.get('content', {}).get('words', {})
        if not words_data:
            return []
        
        # En CapCut v167, los timings pueden estar en diferentes lugares
        words_list = words_data.get('text', [])
        start_times = words_data.get('start_time', [])
        end_times = words_data.get('end_time', [])
        
        # Si no hay timings individuales, usar el timing del segmento
        if not start_times or not end_times:
            start = segment.get('target_timerange', {}).get('start', 0)
            duracion = segment.get('target_timerange', {}).get('duration', 0)
            
            # Distribuir timings uniformemente
            paso = duracion // len(words_list) if words_list else 0
            start_times = [start + i * paso for i in range(len(words_list))]
            end_times = [start + (i + 1) * paso for i in range(len(words_list))]
        
        # Construir oracion
        oracion = []
        for i, word in enumerate(words_list):
            palabra_limpia = word.strip()
            
            # Ignorar espacios y caracteres vacíos
            if not palabra_limpia:
                continue
            
            # Obtener timings
            start_us = int(start_times[i]) if i < len(start_times) else 0
            end_us = int(end_times[i]) if i < len(end_times) else 0
            
            # Validar timings
            if end_us <= start_us:
                end_us = start_us + 100_000  # 100ms por defecto
            
            oracion.append({
                "word": palabra_limpia,
                "start_us": start_us,
                "end_us": end_us
            })
        
        return oracion


def main():
    """Script principal."""
    if len(sys.argv) < 2:
        print("Uso: python utils/extract_autocaption.py <ruta_json>")
        print("  Ejemplo: python utils/extract_autocaption.py C:\\Users\\user2\\Desktop\\draft_arrizzo8.json")
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
    print(f"  - Tracks totales: {stats['total_tracks']}")
    print(f"  - Tracks de texto: {stats['tracks_texto']}")
    print(f"  - Segmentos: {stats['segments']}")
    print(f"  - Oraciones extraídas: {stats['oraciones_validas']}")
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
            print(f"  {i+1}. {' '.join(palabras)}")
    else:
        print(f"\n⚠️  No se encontraron oraciones en el JSON")
    
    print(f"\n💡 Próximos pasos:")
    print(f"   1. Verifica las oraciones en: {output_path}")
    print(f"   2. Ejecuta: python test_integration_real.py '{json_path}' 'arrizzo 8' --generate")


if __name__ == '__main__':
    main()

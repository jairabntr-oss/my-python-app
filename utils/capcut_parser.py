"""
Parser para extraer captions del draft_content.json de CapCut v167+

Extrae palabras con timings exactos para procesamiento posterior.
"""

import json
from typing import List, Dict, Tuple, Optional


class CapcutParser:
    """Parser de draft_content.json de CapCut."""
    
    @staticmethod
    def cargar_y_analizar(json_path: str) -> Dict:
        """Carga el JSON y analiza su estructura.
        
        Retorna un diagnóstico de qué secciones contienen captions.
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        analisis = {
            "version": content.get("new_version", "desconocida"),
            "duracion_ms": content.get("duration", 0) / 1000,
            "canvas": content.get("canvas_config"),
            "tracks_encontrados": []
        }
        
        # Analizar tracks
        for i, track in enumerate(content.get("tracks", [])):
            track_info = {
                "index": i,
                "type": track.get("type"),
                "id": track.get("id"),
                "segments": len(track.get("segments", [])),
                "contiene_captions": False,
                "captions_count": 0
            }
            
            # Buscar captions en clips
            for seg in track.get("segments", []):
                if "content" in seg:
                    content_data = seg["content"]
                    if "text" in content_data or "words" in content_data:
                        track_info["contiene_captions"] = True
                        track_info["captions_count"] += 1
            
            analisis["tracks_encontrados"].append(track_info)
        
        return analisis
    
    @staticmethod
    def extraer_captions(json_path: str) -> Tuple[List[List[Dict]], Optional[str]]:
        """Extrae captions con palabras y timings.
        
        Returns:
            (oraciones, error_message)
            oraciones: lista de listas de palabras
            error_message: descripción si algo falla
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except Exception as e:
            return [], f"Error leyendo JSON: {e}"
        
        oraciones = []
        
        # Buscar en tracks
        for track in content.get("tracks", []):
            # Saltar tracks que no sean de texto
            if track.get("type") not in ["text", 3, "3"]:
                continue
            
            # Procesar segmentos
            for segment in track.get("segments", []):
                # Estructura 1: segment.content.words (más común)
                if "content" in segment:
                    contenido = segment["content"]
                    
                    # Caso A: Palabras explícitas
                    if "words" in contenido:
                        palabras = CapcutParser._procesar_palabras(
                            contenido["words"]
                        )
                        if palabras:
                            oraciones.append(palabras)
                    
                    # Caso B: Texto completo (necesita split)
                    elif "text" in contenido and isinstance(contenido["text"], str):
                        texto = contenido["text"].strip()
                        if texto:
                            # Crear palabras sintéticas con timing
                            start = segment.get("target_timerange", {}).get("start", 0)
                            duracion = segment.get("target_timerange", {}).get("duration", 0)
                            
                            palabras_split = CapcutParser._split_texto_con_timing(
                                texto, start, duracion
                            )
                            if palabras_split:
                                oraciones.append(palabras_split)
        
        if not oraciones:
            return [], "No se encontraron captions en el JSON"
        
        return oraciones, None
    
    @staticmethod
    def _procesar_palabras(words_list: List[Dict]) -> List[Dict]:
        """Convierte la lista de palabras de CapCut al formato estándar."""
        palabras_procesadas = []
        
        for word_data in words_list:
            # Estructura típica de CapCut
            palabra = {
                "word": word_data.get("text", "") or word_data.get("content", ""),
                "start_us": int(word_data.get("startTime", word_data.get("start", 0))),
                "end_us": int(word_data.get("endTime", word_data.get("end", 0)))
            }
            
            if palabra["word"]:  # Solo si tiene texto
                palabras_procesadas.append(palabra)
        
        return palabras_procesadas
    
    @staticmethod
    def _split_texto_con_timing(texto: str, start_us: int, duracion_us: int) -> List[Dict]:
        """Divide un texto en palabras con timing distribuido uniformemente."""
        palabras = texto.split()
        if not palabras:
            return []
        
        paso = duracion_us // len(palabras) if palabras else duracion_us
        resultado = []
        
        for i, palabra in enumerate(palabras):
            resultado.append({
                "word": palabra,
                "start_us": start_us + (i * paso),
                "end_us": start_us + ((i + 1) * paso)
            })
        
        return resultado
    
    @staticmethod
    def diagnosticar_y_mostrar(json_path: str) -> None:
        """Diagnostica el JSON y muestra info en consola."""
        print(f"\n📊 Analizando: {json_path}\n")
        
        # Análisis general
        analisis = CapcutParser.cargar_y_analizar(json_path)
        print(f"✅ Versión CapCut: {analisis['version']}")
        print(f"✅ Duración: {analisis['duracion_ms']:.0f}ms")
        print(f"✅ Canvas: {analisis['canvas']}")
        print(f"\n📍 Tracks encontrados: {len(analisis['tracks_encontrados'])}")
        
        for track_info in analisis['tracks_encontrados']:
            print(f"  Track {track_info['index']}: type={track_info['type']}, "
                  f"segments={track_info['segments']}, "
                  f"captions={track_info['captions_count']}")
        
        # Extraer captions
        print(f"\n🔍 Extrayendo captions...\n")
        oraciones, error = CapcutParser.extraer_captions(json_path)
        
        if error:
            print(f"❌ {error}")
            return
        
        print(f"✅ Oraciones encontradas: {len(oraciones)}")
        total_palabras = sum(len(o) for o in oraciones)
        print(f"✅ Total de palabras: {total_palabras}")
        
        # Mostrar primeras 3 oraciones
        print(f"\n📝 Primeras 3 oraciones:")
        for i, oracion in enumerate(oraciones[:3]):
            print(f"\n  Oración {i + 1}: {len(oracion)} palabras")
            for j, palabra in enumerate(oracion[:5]):  # Primeras 5 palabras
                print(f"    {j + 1}. '{palabra['word']}' "
                      f"[{palabra['start_us']/1e6:.3f}s - {palabra['end_us']/1e6:.3f}s]")
            if len(oracion) > 5:
                print(f"    ... ({len(oracion) - 5} más)")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        json_path = sys.argv[1]
    else:
        json_path = r"C:\Users\user2\Desktop\draft_arrizzo8.json"
    
    CapcutParser.diagnosticar_y_mostrar(json_path)

"""
Parser para extraer captions del draft_content.json de CapCut v167+

Extrae palabras con timings exactos para procesamiento posterior.
"""

import json
from typing import List, Dict, Tuple, Optional
from pathlib import Path


class CapcutParser:
    """Parser de draft_content.json de CapCut."""
    
    @staticmethod
    def cargar_y_analizar(json_path: str) -> Dict:
        """Carga el JSON y analiza su estructura.
        
        Retorna un diagnóstico de qué secciones contienen captions.
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        
        analisis = {\n            "version": content.get("new_version", "desconocida"),
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
            for seg in track.get("segments", []):\n                if "content" in seg:
                    content_data = seg["content"]
                    if "text" in content_data or "words" in content_data:
                        track_info["contiene_captions"] = True
                        track_info["captions_count"] += 1
            
            analisis["tracks_encontrados"].append(track_info)
        
        return analisis
    
    @staticmethod
    def extraer_captions(json_path: str) -> Tuple[List[List[Dict]], Optional[str]]:\n        """Extrae captions con palabras y timings.\n        \n        Returns:\n            (oraciones, error_message)\n            oraciones: lista de listas de palabras\n            error_message: descripción si algo falla\n        \"\"\"\n        try:\n            with open(json_path, 'r', encoding='utf-8') as f:\n                content = json.load(f)\n        except Exception as e:\n            return [], f\"Error leyendo JSON: {e}\"\n        \n        oraciones = []\n        \n        # Buscar en tracks\n        for track in content.get("tracks", []):\n            # Saltar tracks que no sean de texto\n            if track.get("type") not in ["text", 3, "3"]:\n                continue\n            \n            # Procesar segmentos\n            for segment in track.get("segments", []):\n                # Estructura 1: segment.content.words (más común)\n                if "content" in segment:\n                    contenido = segment["content"]\n                    \n                    # Caso A: Palabras explícitas\n                    if "words" in contenido:\n                        palabras = CapcutParser._procesar_palabras(\n                            contenido["words"]\n                        )\n                        if palabras:\n                            oraciones.append(palabras)\n                    \n                    # Caso B: Texto completo (necesita split)\n                    elif "text" in contenido and isinstance(contenido["text"], str):\n                        texto = contenido["text"].strip()\n                        if texto:\n                            # Crear palabras sintéticas con timing\n                            start = segment.get("target_timerange", {}).get("start", 0)\n                            duracion = segment.get("target_timerange", {}).get("duration", 0)\n                            \n                            palabras_split = CapcutParser._split_texto_con_timing(\n                                texto, start, duracion\n                            )\n                            if palabras_split:\n                                oraciones.append(palabras_split)\n        \n        if not oraciones:\n            return [], \"No se encontraron captions en el JSON\"\n        \n        return oraciones, None\n    \n    @staticmethod\n    def _procesar_palabras(words_list: List[Dict]) -> List[Dict]:\n        \"\"\"Convierte la lista de palabras de CapCut al formato estándar.\"\"\"\n        palabras_procesadas = []\n        \n        for word_data in words_list:\n            # Estructura típica de CapCut\n            palabra = {\n                \"word\": word_data.get(\"text\", \"\") or word_data.get(\"content\", \"\"),\n                \"start_us\": int(word_data.get(\"startTime\", word_data.get(\"start\", 0))),\n                \"end_us\": int(word_data.get(\"endTime\", word_data.get(\"end\", 0)))\n            }\n            \n            if palabra[\"word\"]:  # Solo si tiene texto\n                palabras_procesadas.append(palabra)\n        \n        return palabras_procesadas\n    \n    @staticmethod\n    def _split_texto_con_timing(texto: str, start_us: int, duracion_us: int) -> List[Dict]:\n        \"\"\"Divide un texto en palabras con timing distribuido uniformemente.\"\"\"\n        palabras = texto.split()\n        if not palabras:\n            return []\n        \n        paso = duracion_us // len(palabras) if palabras else duracion_us\n        resultado = []\n        \n        for i, palabra in enumerate(palabras):\n            resultado.append({\n                \"word\": palabra,\n                \"start_us\": start_us + (i * paso),\n                \"end_us\": start_us + ((i + 1) * paso)\n            })\n        \n        return resultado\n    \n    @staticmethod\n    def diagnosticar_y_mostrar(json_path: str) -> None:\n        \"\"\"Diagnostica el JSON y muestra info en consola.\"\"\"\n        print(f\"\\n📊 Analizando: {json_path}\\n\")\n        \n        # Análisis general\n        analisis = CapcutParser.cargar_y_analizar(json_path)\n        print(f\"✅ Versión CapCut: {analisis['version']}\")\n        print(f\"✅ Duración: {analisis['duracion_ms']:.0f}ms\")\n        print(f\"✅ Canvas: {analisis['canvas']}\")\n        print(f\"\\n📍 Tracks encontrados: {len(analisis['tracks_encontrados'])}\")\n        \n        for track_info in analisis['tracks_encontrados']:\n            print(f\"  Track {track_info['index']}: type={track_info['type']}, \"\n                  f\"segments={track_info['segments']}, \"\n                  f\"captions={track_info['captions_count']}\")\n        \n        # Extraer captions\n        print(f\"\\n🔍 Extrayendo captions...\\n\")\n        oraciones, error = CapcutParser.extraer_captions(json_path)\n        \n        if error:\n            print(f\"❌ {error}\")\n            return\n        \n        print(f\"✅ Oraciones encontradas: {len(oraciones)}\")\n        total_palabras = sum(len(o) for o in oraciones)\n        print(f\"✅ Total de palabras: {total_palabras}\")\n        \n        # Mostrar primeras 3 oraciones\n        print(f\"\\n📝 Primeras 3 oraciones:\")\n        for i, oracion in enumerate(oraciones[:3]):\n            print(f\"\\n  Oración {i + 1}: {len(oracion)} palabras\")\n            for j, palabra in enumerate(oracion[:5]):  # Primeras 5 palabras\n                print(f\"    {j + 1}. '{palabra['word']}' \"\n                      f\"[{palabra['start_us']/1e6:.3f}s - {palabra['end_us']/1e6:.3f}s]\")\n            if len(oracion) > 5:\n                print(f\"    ... ({len(oracion) - 5} más)\")\n\n\nif __name__ == \"__main__\":\n    import sys\n    \n    if len(sys.argv) > 1:\n        json_path = sys.argv[1]\n    else:\n        json_path = r\"C:\\Users\\user2\\Desktop\\draft_arrizzo8.json\"\n    \n    CapcutParser.diagnosticar_y_mostrar(json_path)\n
"""
CapcutEngine - Integración con CapCut para generar subtítulos automáticos
Usa pycapcut para acceder a los drafts y aplicar el formato aprendido
"""

from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from .learning_engine import LearningEngine


class CapcutEngine:
    """
    Motor para trabajar con CapCut usando pycapcut.
    Genera subtítulos con estilo karaoke acumulativo basado en patrones aprendidos.
    """
    
    def __init__(self, learning_engine: Optional[LearningEngine] = None):
        """
        Args:
            learning_engine: instancia de LearningEngine para usar estilos guardados
        """
        self.learning_engine = learning_engine or LearningEngine()
        self.config = self.learning_engine.profile
        self.visual_settings = self.learning_engine.get_visual_settings()
        
        # Intentar importar pycapcut
        try:
            import pycapcut as cc
            self.cc = cc
            self.pycapcut_available = True
        except ImportError:
            print("⚠️  pycapcut no está instalado. Instala con: pip install pycapcut")
            self.pycapcut_available = False
            self.cc = None
    
    def get_drafts_folder(self) -> Path:
        """Retorna la carpeta de drafts de CapCut."""
        draft_folder = self.config["capcut_paths"]["drafts_folder"]
        return Path(draft_folder)
    
    def list_projects(self) -> List[str]:
        """Lista todos los drafts disponibles en CapCut."""
        if not self.pycapcut_available:
            return []
        
        try:
            draft_folder = self.cc.DraftFolder(str(self.get_drafts_folder()))
            return draft_folder.list_drafts()
        except Exception as e:
            print(f"❌ Error listando proyectos: {e}")
            return []
    
    def load_project(self, project_name: str):
        """Carga un proyecto de CapCut."""
        if not self.pycapcut_available:
            raise RuntimeError("pycapcut no está disponible")
        
        try:
            draft_folder = self.cc.DraftFolder(str(self.get_drafts_folder()))
            script = draft_folder.load_template(project_name)
            return script
        except Exception as e:
            print(f"❌ Error cargando proyecto '{project_name}': {e}")
            return None
    
    def extract_captions_from_draft(self, project_name: str) -> List[List[Dict[str, Any]]]:
        """Extrae los captions del draft_content.json.

        Delega en AutocaptionExtractor, la ÚNICA fuente de verdad para
        parsear drafts (lee content como JSON string + words[] en
        microsegundos y filtra solo el auto-caption sin editar).

        Antes este método parseaba `track["clips"][...]["words"]` con campos
        `startTime`/`endTime`, una estructura que NO existe en el
        draft_content.json real de CapCut (los segmentos viven en
        `track["segments"]` y las palabras en `materials.texts[].content`).
        Por eso devolvía siempre [] y la CLI decía "No se encontraron
        captions".
        """
        content_file = self.get_drafts_folder() / project_name / "draft_content.json"

        if not content_file.exists():
            print(f"⚠️  No se encontró {content_file}")
            return []

        from utils.extract_autocaption import AutocaptionExtractor

        try:
            oraciones, _stats = AutocaptionExtractor.extract(str(content_file))
            return oraciones
        except Exception as e:
            print(f"❌ Error extrayendo captions: {e}")
            return []
    
    def calculate_word_positions(self, word_list: List[Dict[str, Any]], 
                                 y_base: float = 0.0) -> List[Tuple[float, float]]:
        """Calcula las posiciones X, Y para cada palabra usando el patrón de zigzag."""
        posiciones = []
        cajas_ocupadas = []
        y_actual = y_base
        
        for i, word_data in enumerate(word_list):
            texto = word_data.get("word", "")
            largo = len(texto)
            
            # Zigzag: alternar izquierda-derecha
            if i % 2 == 0:
                x = self.visual_settings["anchor_left"]
            else:
                x = self.visual_settings["anchor_right"]
            
            # Reducir desviación para palabras largas
            if largo >= 8:
                x *= 0.5
            
            # Ancho estimado de la palabra
            ancho_palabra = largo * self.visual_settings["char_width"]
            
            x_min = x - ancho_palabra / 2
            x_max = x + ancho_palabra / 2
            
            # Calcular paso Y según largo de palabra
            if largo <= 3:
                paso_y = self.visual_settings["step_y_short"]
            elif largo <= 7:
                paso_y = self.visual_settings["step_y_medium"]
            else:
                paso_y = self.visual_settings["step_y_long"]
            
            # Sistema anti-colisión
            y_candidata = y_actual
            intentos = 0
            max_intentos = 10
            colision = True
            
            while colision and intentos < max_intentos:
                colision = False
                y_min = y_candidata - 0.05
                y_max = y_candidata + 0.05
                
                for caja in cajas_ocupadas:
                    caja_x_min, caja_x_max, caja_y_min, caja_y_max = caja
                    
                    overlap_x = not (x_max < caja_x_min or x_min > caja_x_max)
                    overlap_y = not (y_max < caja_y_min or y_min > caja_y_max)
                    
                    if overlap_x and overlap_y:
                        colision = True
                        y_candidata += paso_y
                        intentos += 1
                        break
            
            y_actual = y_candidata
            
            # Respetar límites de pantalla
            y_actual = max(self.visual_settings["limit_y_top"],
                          min(self.visual_settings["limit_y_bottom"], y_actual))
            
            cajas_ocupadas.append((x_min, x_max, y_actual - 0.05, y_actual + 0.05))
            posiciones.append((x, y_actual))
            
            y_actual += paso_y
        
        return posiciones
    
    def detect_simultaneous_dialog(self, oraciones: List[List[Dict[str, Any]]]) -> List[Tuple[int, int]]:
        """Detecta pares de oraciones que se superponen en el tiempo."""
        pares = []
        umbral = self.visual_settings["overlap_threshold_us"]
        
        for i in range(len(oraciones) - 1):
            fin_actual = oraciones[i][-1]["end_us"]
            inicio_siguiente = oraciones[i + 1][0]["start_us"]
            
            overlap = fin_actual - inicio_siguiente

            # >= para ser consistente con SubtitleEngine._detectar_overlap_real
            # (antes era > y los dos caminos discrepaban en el caso borde).
            if overlap >= umbral:
                pares.append((i, i + 1))
        
        return pares
    
    def split_long_sentence(self, oracion: List[Dict[str, Any]], 
                           max_palabras: Optional[int] = None) -> List[List[Dict[str, Any]]]:
        """Divide una oración larga en bloques más pequeños."""
        if max_palabras is None:
            max_palabras = self.visual_settings["max_words_per_block"]
        
        if len(oracion) <= max_palabras:
            return [oracion]
        
        bloques = []
        bloque_actual = []
        
        for i, palabra in enumerate(oracion):
            bloque_actual.append(palabra)
            
            if len(bloque_actual) >= max_palabras:
                bloques.append(bloque_actual)
                bloque_actual = []
            elif i < len(oracion) - 1:
                gap = oracion[i + 1]["start_us"] - palabra["end_us"]
                if gap >= 60_000:  # 60ms
                    bloques.append(bloque_actual)
                    bloque_actual = []
        
        if bloque_actual:
            bloques.append(bloque_actual)
        
        return bloques
    
    def suggest_format_adjustments(self, project_name: str) -> Dict[str, Any]:
        """Analiza un proyecto y sugiere ajustes de formato."""
        try:
            oraciones = self.extract_captions_from_draft(project_name)
            
            if not oraciones:
                return {"message": "No hay captions"}
            
            # Analizar características
            total_palabras = sum(len(o) for o in oraciones)
            palabra_mas_larga = max(
                (len(p["word"]) for o in oraciones for p in o),
                default=0
            )
            palabra_mas_corta = min(
                (len(p["word"]) for o in oraciones for p in o),
                default=0
            )
            
            return {
                "project": project_name,
                "total_sentences": len(oraciones),
                "total_words": total_palabras,
                "longest_word": palabra_mas_larga,
                "shortest_word": palabra_mas_corta,
                "avg_sentence_length": total_palabras / len(oraciones) if oraciones else 0,
                "current_scale": self.visual_settings["scale"],
                "current_char_width": self.visual_settings["char_width"],
                "recommendations": [
                    "Aumentar char_width si las palabras se solapan",
                    "Reducir scale si el texto se ve muy grande",
                    "Ajustar step_y según densidad de palabras"
                ]
            }
        
        except Exception as e:
            return {"error": str(e)}

    def generate_subtitles_for_project(
        self,
        project_name: str,
        track_name: str = "AUTO_subtitles",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Pipeline completo: extrae captions y genera subtítulos karaoke.

        Args:
            project_name: nombre del draft de CapCut.
            track_name: nombre del track de texto a crear.
            dry_run: si True, sólo simula sin escribir en disco.

        Returns:
            Dict con estadísticas de la generación o clave "error".
        """
        try:
            # 1. Extraer captions del draft
            oraciones = self.extract_captions_from_draft(project_name)
            if not oraciones:
                return {"error": "No se encontraron captions en el proyecto"}

            # 2. Detectar diálogos simultáneos
            pares_overlap = self.detect_simultaneous_dialog(oraciones)

            # 3. Dividir oraciones largas en bloques
            bloques: List[List[Dict[str, Any]]] = []
            for oracion in oraciones:
                bloques.extend(self.split_long_sentence(oracion))

            # 4. Calcular posiciones (zigzag + anti-colisión)
            total_palabras = sum(len(b) for b in bloques)

            if dry_run:
                return {
                    "dry_run": True,
                    "total_words": total_palabras,
                    "total_blocks": len(bloques),
                    "simultaneous_dialogs": len(pares_overlap),
                    "track_created": track_name,
                }

            # 5. Escribir en disco usando SubtitleEngine
            from .subtitle_engine import SubtitleEngine

            profile = {
                **self.config.get("text_format", {}),
                **self.visual_settings,
                "font_path": self.config.get("text_format", {}).get("font_path", ""),
                "text_size": self.config.get("text_format", {}).get("size", 30),
                "text_color": self.config.get("text_format", {}).get("color", "#FFFFFF"),
                "scale_x": self.visual_settings.get("scale", 3.037),
                "scale_y": self.visual_settings.get("scale", 3.037),
                "shadow_enabled": self.config.get("text_format", {}).get("shadow", {}).get("enabled", True),
                "shadow_color": self.config.get("text_format", {}).get("shadow", {}).get("color", "#000000"),
                "shadow_alpha": self.config.get("text_format", {}).get("shadow", {}).get("alpha", 0.33),
                "shadow_distance": self.config.get("text_format", {}).get("shadow", {}).get("distance", 17.0),
                "shadow_angle": self.config.get("text_format", {}).get("shadow", {}).get("angle", -115.9),
            }

            engine = SubtitleEngine.from_draft(
                str(self.get_drafts_folder()), project_name, profile
            )
            resultado = engine.generate(oraciones)

            return {
                "total_words": resultado.get("total_palabras", total_palabras),
                "total_blocks": resultado.get("total_bloques", len(bloques)),
                "simultaneous_dialogs": resultado.get("pares_overlap", len(pares_overlap)),
                "track_created": track_name,
            }

        except Exception as e:
            return {"error": str(e)}

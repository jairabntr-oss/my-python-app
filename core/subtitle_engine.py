"""
SubtitleEngine - Motor para procesar y generar subtítulos
"""

from typing import List, Dict, Any


class SubtitleEngine:
    """Motor para procesar y transformar subtítulos con estilos aprendidos."""
    
    def __init__(self):
        self.subtitles = []
    
    def load_subtitles(self, file_path: str) -> bool:
        """Carga subtítulos de un archivo."""
        try:
            # TODO: Soportar diferentes formatos (SRT, VTT, ASS, etc.)
            return True
        except Exception as e:
            print(f"Error cargando subtítulos: {e}")
            return False
    
    def display_subtitles(self) -> List[Dict[str, Any]]:
        """Retorna los subtítulos cargados."""
        return self.subtitles
    
    def process_subtitles(self, transform_func=None) -> List[Dict[str, Any]]:
        """Procesa subtítulos aplicando transformaciones."""
        if transform_func is None:
            return self.subtitles
        
        return [transform_func(sub) for sub in self.subtitles]
    
    def clear_subtitles(self) -> None:
        """Limpia la lista de subtítulos."""
        self.subtitles = []
    
    def add_subtitle(self, start_time: float, end_time: float, text: str, 
                    style: Dict[str, Any] = None) -> None:
        """Agrega un subtítulo nuevo."""
        subtitle = {
            "start_time": start_time,
            "end_time": end_time,
            "text": text,
            "style": style or {}
        }
        self.subtitles.append(subtitle)

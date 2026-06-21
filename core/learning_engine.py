"""
LearningEngine - Aprende tus patrones de edición y los guarda para reutilizar
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


class LearningEngine:
    """
    Aprende patrones de edición del usuario y aplica estilos automáticamente.
    Guarda configuraciones en JSON para que se reutilicen en nuevos videos.
    """
    
    def __init__(self, profile_path: str = "config/user_profile.json"):
        self.profile_path = Path(profile_path)
        self.profile = self._load_profile()
    
    def _load_profile(self) -> Dict[str, Any]:
        """Carga el perfil del usuario si existe, sino crea uno nuevo."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Error al cargar perfil: {e}. Creando nuevo...")
                return self._create_default_profile()
        return self._create_default_profile()
    
    def _create_default_profile(self) -> Dict[str, Any]:
        """Crea un perfil por defecto con estructura base."""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            
            # Formato de texto - lo que ya aprendió de tus videos
            "text_format": {
                "font": "Poppins-Bold",
                "font_id": "7312373689708712449",
                "font_path": r"C:\Users\user2\AppData\Local\CapCut\User Data\Cache\effect\7312373689708712449\d090413fb1d5672cdf7177fea62fbccd\Poppins-Bold.ttf",
                "size": 30,
                "color": "#FFFFFF",
                "bold": True,
                "italic": False,
                "shadow": {
                    "enabled": True,
                    "color": "#000000",
                    "alpha": 0.33,
                    "distance": 17.0,
                    "angle": -115.9
                }
            },
            
            # Configuración visual (zigzag, posicionamiento, etc.)
            "visual_settings": {
                "scale": 1.67,  # 167%
                "anchor_left": -0.25,
                "anchor_right": 0.25,
                "char_width": 0.15,
                "step_y_short": 0.05,   # 1-3 letras
                "step_y_medium": 0.08,  # 4-7 letras
                "step_y_long": 0.10,    # 8+ letras
                "limit_y_top": -0.70,
                "limit_y_bottom": 0.70,
                "max_words_per_block": 5,
                "overlap_threshold_us": 150_000  # 150ms
            },
            
            # Carpetas y rutas del usuario
            "capcut_paths": {
                "drafts_folder": r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft",
                "cache_folder": r"C:\Users\user2\AppData\Local\CapCut\User Data\Cache"
            },
            
            # Proyectos (drafts) que ha editado
            "projects": {},
            
            # Historial de acciones para aprender patrones
            "editing_history": [],
            
            # Sugerencias automáticas basadas en patrones
            "auto_suggestions": True,
            
            "last_used": None
        }
    
    def save_profile(self) -> None:
        """Guarda el perfil en el archivo JSON."""
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile["updated_at"] = datetime.now().isoformat()
        
        with open(self.profile_path, 'w', encoding='utf-8') as f:
            json.dump(self.profile, f, indent=2, ensure_ascii=False)
    
    def set_text_format(self, **kwargs) -> None:
        """
        Actualiza el formato de texto aprendiendo de tus cambios.
        
        Args:
            font: nombre de la fuente
            size: tamaño en pixels
            color: color en formato #RRGGBB
            bold: si está en negrita
            italic: si está en cursiva
            shadow_color: color de sombra
            shadow_alpha: transparencia de sombra (0-1)
            shadow_distance: distancia de sombra
            shadow_angle: ángulo de sombra
        """
        # Actualizar solo los campos que se pasen
        for key, value in kwargs.items():
            if key.startswith('shadow_'):
                # Manejo especial para propiedades de sombra
                shadow_key = key.replace('shadow_', '')
                self.profile["text_format"]["shadow"][shadow_key] = value
            elif key in self.profile["text_format"]:
                self.profile["text_format"][key] = value
        
        self.save_profile()
    
    def apply_text_format(self, subtitle_text: str) -> Dict[str, Any]:
        """
        Aplica automáticamente el formato guardado a un texto.
        
        Returns:
            dict con el texto y su estilo
        """
        return {
            "text": subtitle_text,
            "style": self.profile["text_format"].copy()
        }
    
    def get_visual_settings(self) -> Dict[str, Any]:
        """Retorna todas las configuraciones visuales aprendidas."""
        return self.profile["visual_settings"].copy()
    
    def set_visual_settings(self, **kwargs) -> None:
        """Actualiza las configuraciones visuales (escala, posicionamiento, etc.)"""
        for key, value in kwargs.items():
            if key in self.profile["visual_settings"]:
                self.profile["visual_settings"][key] = value
        self.save_profile()
    
    def register_project(self, project_name: str, config: Dict[str, Any]) -> None:
        """
        Registra un proyecto (draft de CapCut) con su configuración específica.
        Esto permite que próximas veces use el mismo estilo automáticamente.
        
        Args:
            project_name: nombre del draft (ej: "tiggo 4", "arrizzo 8")
            config: diccionario con configuración específica del proyecto
        """
        if "projects" not in self.profile:
            self.profile["projects"] = {}
        
        self.profile["projects"][project_name] = {
            "config": config,
            "last_used": datetime.now().isoformat(),
            "version": 1
        }
        self.save_profile()
    
    def get_project_config(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Retorna la configuración guardada de un proyecto si existe."""
        if project_name in self.profile.get("projects", {}):
            return self.profile["projects"][project_name]["config"]
        return None
    
    def log_editing_action(self, action_type: str, data: Dict[str, Any], 
                          project_name: Optional[str] = None) -> None:
        """
        Registra cada acción de edición para aprender patrones.
        
        Args:
            action_type: tipo de acción (ej: "apply_format", "adjust_position")
            data: datos específicos de la acción
            project_name: proyecto en el que se hizo la acción
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action_type,
            "project": project_name,
            "data": data
        }
        
        if "editing_history" not in self.profile:
            self.profile["editing_history"] = []
        
        self.profile["editing_history"].append(entry)
        
        # Mantener solo los últimos 100 registros
        if len(self.profile["editing_history"]) > 100:
            self.profile["editing_history"] = self.profile["editing_history"][-100:]
        
        self.profile["last_used"] = datetime.now().isoformat()
        self.save_profile()
    
    def get_editing_suggestions(self) -> Dict[str, Any]:
        """
        Analiza el historial de ediciones y sugiere configuraciones.
        Retorna un resumen de lo que más haces.
        """
        if not self.profile.get("editing_history"):
            return {
                "message": "Sin historial aún",
                "suggestions": []
            }
        
        # Contar acciones por tipo
        action_counts = {}
        for entry in self.profile["editing_history"]:
            action = entry["action"]
            action_counts[action] = action_counts.get(action, 0) + 1
        
        # Acciones más frecuentes
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "total_actions": len(self.profile["editing_history"]),
            "most_common_actions": top_actions,
            "current_settings": {
                "text": self.profile["text_format"],
                "visual": self.profile["visual_settings"]
            },
            "projects_edited": list(self.profile.get("projects", {}).keys())
        }
    
    def reset_to_defaults(self) -> None:
        """Resetea el perfil a configuración por defecto."""
        self.profile = self._create_default_profile()
        self.save_profile()
    
    def export_settings(self, output_path: str) -> None:
        """Exporta las configuraciones actuales a un JSON."""
        export_data = {
            "text_format": self.profile["text_format"],
            "visual_settings": self.profile["visual_settings"],
            "capcut_paths": self.profile["capcut_paths"]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    def import_settings(self, input_path: str) -> None:
        """Importa configuraciones de otro JSON."""
        with open(input_path, 'r', encoding='utf-8') as f:
            imported = json.load(f)
        
        if "text_format" in imported:
            self.profile["text_format"].update(imported["text_format"])
        if "visual_settings" in imported:
            self.profile["visual_settings"].update(imported["visual_settings"])
        if "capcut_paths" in imported:
            self.profile["capcut_paths"].update(imported["capcut_paths"])
        
        self.save_profile()

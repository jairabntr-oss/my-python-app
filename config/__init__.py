"""
Configuración global de la aplicación Subtilearn.

Exporta constantes usadas por todos los módulos.
"""

import json
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent

PATHS = {
    "backups": _BASE_DIR / "backups",
    "assets":  _BASE_DIR / "assets",
    "logs":    _BASE_DIR / "logs",
    "config":  _BASE_DIR / "config",
}

# ─── Nombres de tracks de auto-caption de CapCut ────────────────────────────
AUTO_CAPTION_NAMES = [
    "auto_caption",
    "Reconocimiento de voz",
    "Auto captions",
    "自动字幕",
]

# ─── UI ───────────────────────────────────────────────────────────────────────
APP_WIDTH       = 900
APP_HEIGHT      = 600
APP_MIN_WIDTH   = 700
APP_MIN_HEIGHT  = 500

COLORS = {
    "banner":     "#D32F2F",
    "active_btn": ("#1565C0", "#0D47A1"),
    "success":    "#2E7D32",
    "danger":     "#C62828",
    "warning":    "#F57C00",
    "text":       ("#1A1A1A", "#E0E0E0"),
    "bg":         ("#F5F5F5", "#1E1E1E"),
}

# ─── Settings (cargados desde settings.json) ──────────────────────────────────
_settings_path = _BASE_DIR / "config" / "settings.json"

try:
    with open(_settings_path, "r", encoding="utf-8") as _f:
        settings = json.load(_f)
except Exception:
    settings = {}


def cargar_perfil_estilo() -> dict:
    """Carga config/user_profile.json (el estilo REAL calibrado por el
    usuario, ver PLAN_TECNICO_COMPLETO.md) y lo traduce al formato plano
    que espera SubtitleEngine. Si no existe o esta incompleto, cae en los
    mismos defaults documentados (Poppins-Bold, sombra calibrada).

    Sin esto, ningun script estaba leyendo user_profile.json: el motor
    usaba valores sueltos hardcodeados y el resultado salia sin sombra ni
    fuente custom (texto "feo/default" en CapCut).
    """
    path = _BASE_DIR / "config" / "user_profile.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            perfil = json.load(f)
    except Exception:
        perfil = {}

    tf = perfil.get("text_format", {}) or {}
    sh = tf.get("shadow", {}) or {}
    vs = perfil.get("visual_settings", {}) or {}

    return {
        "text_size": tf.get("size", 30),
        "text_color": tf.get("color", "#FFFFFF"),
        "bold": tf.get("bold", True),
        "font_path": tf.get("font_path"),
        "font_name": tf.get("font"),
        "scale_x": vs.get("scale", 3.037),
        "scale_y": vs.get("scale", 3.037),
        "shadow_enabled": sh.get("enabled", True),
        "shadow_color": sh.get("color", "#000000"),
        "shadow_alpha": sh.get("alpha", 0.33),
        "shadow_distance": sh.get("distance", 17.0),
        "shadow_angle": sh.get("angle", -115.9),
        "ancla_izquierda": vs.get("anchor_left", -0.20),
        "ancla_derecha": vs.get("anchor_right", 0.20),
        "ancho_por_caracter": vs.get("char_width", 0.15),
        "max_palabras_por_bloque": vs.get("max_words_per_block", 5),
    }

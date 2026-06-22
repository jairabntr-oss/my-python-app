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

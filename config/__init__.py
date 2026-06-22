"""
Configuración central de la aplicación.
Centraliza constantes de UI, rutas y nombres de tracks para CapCut.
"""

from pathlib import Path

# ── Dimensiones de la ventana principal ──────────────────────────────────────
APP_WIDTH = 1200
APP_HEIGHT = 800
APP_MIN_WIDTH = 900
APP_MIN_HEIGHT = 600

# ── Paleta de colores UI ──────────────────────────────────────────────────────
COLORS: dict = {
    "banner": "#E53935",
    "active_btn": ("#1F6AA5", "#144870"),
    "success": "#2E7D32",
    "danger": "#C62828",
}

# ── Rutas de la aplicación ────────────────────────────────────────────────────
PATHS: dict = {
    "backups": Path("backups"),
    "logs": Path("logs"),
}

# ── Nombres de tracks de auto-caption de CapCut ───────────────────────────────
AUTO_CAPTION_NAMES: list[str] = [
    "auto_caption",
    "Reconocimiento de voz",
    "Auto captions",
]

__all__ = [
    "APP_WIDTH",
    "APP_HEIGHT",
    "APP_MIN_WIDTH",
    "APP_MIN_HEIGHT",
    "COLORS",
    "PATHS",
    "AUTO_CAPTION_NAMES",
]

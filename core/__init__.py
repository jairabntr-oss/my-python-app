"""
Core module - contiene los motores principales de la aplicación
"""
from .learning_engine import LearningEngine
from .capcut_engine import CapcutEngine
from .subtitle_engine import SubtitleEngine
from .logger import logger

__all__ = ['LearningEngine', 'CapcutEngine', 'SubtitleEngine', 'logger']

"""
Logger - Sistema de logging para la aplicación
"""

import logging
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """Retorna un logger configurado.

    Idempotente: si el logger ya tiene handlers (porque get_logger se llamó
    antes con el mismo nombre), los reutiliza en vez de agregar handlers
    duplicados (que harían que cada línea de log se imprima N veces).
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    # Handler para archivo
    file_handler = logging.FileHandler(log_path / "app.log")
    file_handler.setLevel(logging.DEBUG)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formato
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


logger = get_logger("my-python-app")

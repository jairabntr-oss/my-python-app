"""
Cleaner - Elimina tracks residuales de generaciones previas en un script de CapCut.

Los tracks que comienzan con el prefijo "AUTO_" son creados por esta aplicación
y deben limpiarse antes de una nueva generación para evitar duplicados.
"""

from typing import Any


PREFIJO_AUTO = "AUTO_"


class Cleaner:
    """Limpia tracks de texto y audio residuales de generaciones anteriores."""

    def __init__(self, script: Any) -> None:
        """
        Args:
            script: script de CapCut cargado con pycapcut (load_template).
        """
        self.script = script

    def limpiar_tracks_texto(self) -> int:
        """Elimina tracks de texto cuyo nombre empiece con 'AUTO_'.

        Returns:
            Número de tracks eliminados.
        """
        return self._limpiar_tracks(tipo="text")

    def limpiar_tracks_audio(self) -> int:
        """Elimina tracks de audio cuyo nombre empiece con 'AUTO_'.

        Returns:
            Número de tracks eliminados.
        """
        return self._limpiar_tracks(tipo="audio")

    def _limpiar_tracks(self, tipo: str) -> int:
        """Elimina tracks del tipo indicado que tengan prefijo AUTO_.

        Args:
            tipo: "text" o "audio".

        Returns:
            Número de tracks eliminados.
        """
        eliminados = 0
        tracks_a_borrar = [
            track
            for track in getattr(self.script, "imported_tracks", [])
            if getattr(track, "name", "").startswith(PREFIJO_AUTO)
            and getattr(track, "type", "") == tipo
        ]
        for track in tracks_a_borrar:
            try:
                self.script.remove_track(track)
                eliminados += 1
            except AttributeError:
                # Fallback: intentar remover por nombre si la API lo admite
                pass
        return eliminados


# ── Funciones utilitarias de limpieza de texto ───────────────────────────────

def clean_data(data: str) -> str:
    """Retorna la cadena sin espacios en los extremos."""
    return data.strip()


def remove_empty_entries(data_list: list) -> list:
    """Retorna la lista sin entradas vacías o falsy."""
    return [entry for entry in data_list if entry]


def normalize_text(text: str) -> str:
    """Retorna el texto en minúsculas para normalización."""
    return text.lower()

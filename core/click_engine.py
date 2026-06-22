"""
Motor de clicks de audio sincronizados.

Resuelve errores del handoff:
- Error #12: add_material() EXPLÍCITO (AudioSegment no lo hace automáticamente)
- Error #13: 2 clicks por oración (primera + última), NO 3
"""

import os
from typing import List

try:
    import pycapcut as cc
    _PYCAPCUT_AVAILABLE = True
except ImportError:
    cc = None  # type: ignore[assignment]
    _PYCAPCUT_AVAILABLE = False


class ClickEngine:
    """Motor de generación de clicks de audio sincronizados."""

    TRACK_NAME = "AUTO_clicks"
    VOLUMEN_DEFAULT = 0.4
    MODO_DEFAULT = "2_por_oracion"  # primera + última

    def __init__(self, script, ruta_sonido: str):
        """Inicializa el motor de clicks.

        Args:
            script: script de CapCut ya cargado (ScriptFile)
            ruta_sonido: ruta al archivo de audio del click
        """
        self.script = script
        self.ruta_sonido = ruta_sonido
        self.material_audio = None

    def generate(self, oraciones: List[List[dict]], modo: str = None) -> dict:
        """Genera clicks sincronizados.

        Args:
            oraciones: lista de oraciones (cada una es lista de palabras)
            modo: "2_por_oracion" (default) o "3_por_oracion"

        Returns:
            Dict con resultado
        """
        if not _PYCAPCUT_AVAILABLE:
            raise RuntimeError("pycapcut no está instalado. Ejecuta: pip install pycapcut")

        modo = modo or self.MODO_DEFAULT

        if not os.path.exists(self.ruta_sonido):
            raise FileNotFoundError(f"Sonido no encontrado: {self.ruta_sonido}")

        # ⚠️ CRÍTICO (Error #12): Crear material Y registrarlo EXPLÍCITAMENTE
        self.material_audio = cc.AudioMaterial(
            self.ruta_sonido,
            material_name="click_subtitulo",
        )
        self.script.add_material(self.material_audio)

        # Calcular timestamps según modo
        timestamps = self._calcular_timestamps(oraciones, modo)

        # Crear track de audio si no existe
        self._asegurar_track()

        # Insertar clicks
        total_dur = self.material_audio.duration
        for i, ts in enumerate(timestamps):
            # Calcular duración disponible hasta el siguiente click
            if i + 1 < len(timestamps):
                duracion = min(total_dur, timestamps[i + 1] - ts)
            else:
                duracion = total_dur

            duracion = max(duracion, 1_000)  # mínimo 1ms

            segmento = cc.AudioSegment(
                self.material_audio,
                cc.Timerange(int(ts), int(duracion)),
                volume=self.VOLUMEN_DEFAULT,
            )
            self.script.add_segment(segmento, self.TRACK_NAME)

        self.script.save()

        return {
            "success": True,
            "total_clicks": len(timestamps),
            "track_name": self.TRACK_NAME,
            "modo": modo,
        }

    def _calcular_timestamps(self, oraciones: List[List[dict]], modo: str) -> List[int]:
        """Calcula timestamps donde insertar clicks.

        Resuelve Error #13: solo 2 clicks por oración (primera + última).
        """
        timestamps: set = set()

        for oracion in oraciones:
            n = len(oracion)

            if modo == "2_por_oracion":
                indices = [0, n - 1]
            else:
                indices = [0, n // 2, n - 1]

            for idx in indices:
                if 0 <= idx < n:
                    timestamps.add(int(oracion[idx]["start_us"]))

        return sorted(timestamps)

    def _asegurar_track(self) -> None:
        """Crea track de audio si no existe en imported_tracks ni en tracks nuevos."""
        # Revisar imported_tracks (del JSON original)
        for track in self.script.imported_tracks:
            if track.name == self.TRACK_NAME:
                return
        # Revisar tracks nuevos de esta sesión
        if self.TRACK_NAME in self.script.tracks:
            return
        self.script.add_track(cc.TrackType.audio, self.TRACK_NAME)

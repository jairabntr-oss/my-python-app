"""
Servicio orquestador del pipeline completo de generación.

Coordina con un ÚNICO objeto script compartido:
1. Cargar el draft (una sola vez)
2. Limpiar tracks viejos AUTO_ (texto)
3. Generar subtítulos
4. Limpiar tracks viejos AUTO_ (audio) y generar clicks (opcional)
5. Guardado final

Nota: subtitle_engine.generate() y click_engine.generate() ya hacen save()
sobre el MISMO script compartido, por lo que el guardado final queda cubierto.
"""

from typing import List, Optional
from core.subtitle_engine import SubtitleEngine
from core.click_engine import ClickEngine
from core.cleaner import Cleaner

try:
    import pycapcut as cc
    _PYCAPCUT_AVAILABLE = True
except ImportError:
    cc = None  # type: ignore[assignment]
    _PYCAPCUT_AVAILABLE = False


class DraftService:
    """Servicio que orquesta el pipeline completo."""

    def __init__(self, draft_folder: str, profile: dict):
        self.draft_folder = draft_folder
        self.profile = profile

    def generar_completo(
        self,
        draft_name: str,
        oraciones_auto: List[List[dict]],
        sonido_clicks: Optional[str] = None,
        modo_clicks: Optional[str] = None,
    ) -> dict:
        """Ejecuta el pipeline completo: limpia → subtítulos → clicks.

        Usa UN ÚNICO script compartido para todas las operaciones.
        """
        try:
            if not _PYCAPCUT_AVAILABLE:
                raise RuntimeError("pycapcut no está instalado. Ejecuta: pip install pycapcut")

            # 1. Cargar draft (una sola vez)
            draft_folder_obj = cc.DraftFolder(self.draft_folder)
            script = draft_folder_obj.load_template(draft_name)

            # 2. Limpiar tracks AUTO_ de TEXTO
            cleaner = Cleaner(script)
            tracks_limpiados_texto = cleaner.limpiar_tracks_texto()

            # 3. Generar subtítulos (mismo script)
            subtitle_engine = SubtitleEngine(script, self.profile)
            resultado_subtitulos = subtitle_engine.generate(oraciones_auto)

            # 4. Generar clicks (opcional, mismo script)
            resultado_clicks = None
            tracks_limpiados_audio = 0
            if sonido_clicks:
                try:
                    tracks_limpiados_audio = cleaner.limpiar_tracks_audio()
                    click_engine = ClickEngine(script, sonido_clicks)
                    resultado_clicks = click_engine.generate(oraciones_auto, modo=modo_clicks)
                except Exception as e:
                    resultado_clicks = {"success": False, "error": f"Error generando clicks: {e}"}
                    script.save()  # no perder los subtítulos si fallan los clicks

            return {
                "success": True,
                "draft_name": draft_name,
                "summary": {
                    "tracks_limpiados_texto": tracks_limpiados_texto,
                    "tracks_limpiados_audio": tracks_limpiados_audio,
                    "total_palabras_generadas": resultado_subtitulos.get("total_palabras", 0),
                    "total_bloques": resultado_subtitulos.get("total_bloques", 0),
                    "pares_overlap": resultado_subtitulos.get("pares_overlap", 0),
                    "total_tracks": resultado_subtitulos.get("total_tracks", 0),
                    "total_clicks": (resultado_clicks or {}).get("total_clicks", 0),
                },
                "subtitulos": resultado_subtitulos,
                "clicks": resultado_clicks,
                "status": "Generación completada exitosamente",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "draft_name": draft_name,
                "status": f"Error durante generación: {e}",
            }

    def validar_datos_entrada(self, oraciones_auto: List[List[dict]]) -> tuple:
        """Valida que los datos sean correctos antes de generar."""
        if not oraciones_auto:
            return False, "No hay oraciones"
        for i, oracion in enumerate(oraciones_auto):
            if not isinstance(oracion, list):
                return False, f"Oración {i} no es una lista"
            for j, palabra_data in enumerate(oracion):
                for campo in ("word", "start_us", "end_us"):
                    if campo not in palabra_data:
                        return False, f"Palabra {j} en oración {i}: falta '{campo}'"
        return True, "Datos válidos"

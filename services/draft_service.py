"""
Servicio orquestador del pipeline completo de generación.

Coordina con un único objeto script compartido:
1. Limpieza de tracks viejos (texto)
2. Generación de subtítulos
3. Limpieza de tracks viejos (audio)
4. Generación de clicks (opcional)
5. Guardado final
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
        """Inicializa el servicio.

        Args:
            draft_folder: ruta de drafts de CapCut
            profile: diccionario con configuración de estilos
        """
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

        Usa UN ÚNICO script compartido para todas las operaciones,
        garantizando que la limpieza sea visible por los motores de
        generación y que el guardado final sea coherente.

        Args:
            draft_name: nombre del draft
            oraciones_auto: lista de oraciones con timings
            sonido_clicks: ruta al archivo de audio de clicks (opcional)

        Returns:
            Dict con resultado detallado
        """
        try:
            if not _PYCAPCUT_AVAILABLE:
                raise RuntimeError("pycapcut no está instalado. Ejecuta: pip install pycapcut")

            # ── 1. Cargar draft (una sola vez) ────────────────────────────────
            draft_folder_obj = cc.DraftFolder(self.draft_folder)
            script = draft_folder_obj.load_template(draft_name)

            # ── 2. Limpiar tracks viejos de TEXTO ─────────────────────────────
            cleaner = Cleaner(script)
            tracks_limpiados_texto = cleaner.limpiar_tracks_texto()

            # ── 3. Generar subtítulos (mismo script) ──────────────────────────
            subtitle_engine = SubtitleEngine(script, self.profile)
            resultado_subtitulos = subtitle_engine.generate(oraciones_auto)

            # ── 4. Generar clicks (opcional, mismo script) ────────────────────
            resultado_clicks = None
            tracks_limpiados_audio = 0

            if sonido_clicks:
                try:
                    tracks_limpiados_audio = cleaner.limpiar_tracks_audio()
                    click_engine = ClickEngine(script, sonido_clicks)
                    resultado_clicks = click_engine.generate(oraciones_auto)
                except Exception as e:
                    resultado_clicks = {
                        "success": False,
                        "error": f"Error generando clicks: {str(e)}",
                    }

            # generate() ya llama a script.save() internamente; si solo se
            # generaron subtítulos el save se realizó allí. Si además se
            # generaron clicks, el save del click_engine lo cubre. En el caso
            # de error en clicks, guardamos aquí para no perder los subtítulos.
            if sonido_clicks and resultado_clicks and not resultado_clicks.get("success"):
                script.save()

            return {
                "success": True,
                "draft_name": draft_name,
                "summary": {
                    "tracks_limpiados_texto": tracks_limpiados_texto,
                    "tracks_limpiados_audio": tracks_limpiados_audio,
                    "total_palabras_generadas": resultado_subtitulos.get("total_palabras", 0),
                    "total_bloques": resultado_subtitulos.get("total_bloques", 0),
                    "pares_overlap": resultado_subtitulos.get("pares_overlap", 0),
                },
                "subtitulos": resultado_subtitulos,
                "clicks": resultado_clicks,
                "status": "✅ Generación completada exitosamente",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "draft_name": draft_name,
                "status": f"❌ Error durante generación: {str(e)}",
            }

    def validar_datos_entrada(self, oraciones_auto: List[List[dict]]) -> tuple:
        """Valida que los datos sean correctos antes de generar.

        Returns:
            (es_valido: bool, mensaje: str)
        """
        if not oraciones_auto:
            return False, "No hay oraciones"

        for i, oracion in enumerate(oraciones_auto):
            if not isinstance(oracion, list):
                return False, f"Oración {i} no es una lista"

            for j, palabra_data in enumerate(oracion):
                if "word" not in palabra_data:
                    return False, f"Palabra {j} en oración {i}: falta 'word'"
                if "start_us" not in palabra_data:
                    return False, f"Palabra {j} en oración {i}: falta 'start_us'"
                if "end_us" not in palabra_data:
                    return False, f"Palabra {j} en oración {i}: falta 'end_us'"

        return True, "Datos válidos"

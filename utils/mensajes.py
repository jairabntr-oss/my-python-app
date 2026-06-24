"""
Traduce resultados de analisis y errores tecnicos a mensajes claros y
ACCIONABLES en espanol, para que el usuario sepa exactamente que hacer sin
tener que pedir ayuda externa.

Este modulo es la clave para que el repo sea autosuficiente: cada situacion
problematica conocida (0 oraciones, CapCut abierto, draft sin datos, etc.)
tiene aca un mensaje que explica QUE paso y QUE hacer al respecto, en vez
de un error tecnico crudo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Diagnostico:
    """Resultado de interpretar el estado de un draft.

    nivel: 'ok' | 'aviso' | 'error'
    titulo: linea corta (que paso)
    pasos: instrucciones concretas (que hacer), lista de strings
    puede_continuar: si el usuario puede seguir al paso de generar
    """
    nivel: str
    titulo: str
    pasos: list
    puede_continuar: bool


def interpretar_analisis(result: dict) -> Diagnostico:
    """Convierte el dict de DraftManager.analyze() en un Diagnostico
    accionable.

    Cubre los casos reales que mas confundieron en la practica:
    - 0 oraciones procesables -> falta el auto-caption nativo.
    - Hay tracks AUTO_ residuales -> corrida anterior, se van a limpiar.
    - Todo OK -> listo para generar.
    """
    procesables = result.get("cantidad_oraciones_procesables", 0)
    ya_estiladas = result.get("cantidad_oraciones_ya_estiladas", 0)
    residuales_texto = result.get("tracks_residuales_texto", []) or []
    residuales_audio = result.get("tracks_residuales_audio", []) or []

    # ── Caso 1: no hay nada que procesar ─────────────────────────────────
    if procesables == 0:
        # Distinguir entre "ya estaba todo estilizado" y "no hay
        # auto-caption en absoluto", porque la accion es distinta.
        if ya_estiladas > 0:
            return Diagnostico(
                nivel="aviso",
                titulo="Este proyecto ya parece tener subtitulos estilizados.",
                pasos=[
                    "No se encontro auto-caption nativo SIN editar para procesar.",
                    f"Hay {ya_estiladas} oracion(es) que ya tienen estilo aplicado.",
                    "Si queres regenerar desde cero: en CapCut, borra los",
                    "subtitulos actuales, volve a generar los Subtitulos",
                    "automaticos, guarda, cerra CapCut y volve a analizar.",
                ],
                puede_continuar=False,
            )
        return Diagnostico(
            nivel="error",
            titulo="Este proyecto no tiene subtitulos automaticos para procesar.",
            pasos=[
                "1. Abri este proyecto en CapCut.",
                "2. Clic derecho sobre el clip de video -> 'Subtitulos",
                "   automaticos' (o el boton de Captions/Subtitulos).",
                "3. Espera a que termine de reconocer la voz.",
                "4. Guarda el proyecto (Ctrl+S).",
                "5. CERRA CapCut por completo.",
                "6. Volve aca y presiona 'Analizar' de nuevo.",
            ],
            puede_continuar=False,
        )

    # ── Caso 2: hay datos, pero quedan tracks residuales de antes ────────
    pasos_ok = [
        f"Se encontraron {procesables} oraciones listas para procesar.",
    ]
    if residuales_texto or residuales_audio:
        total_res = len(residuales_texto) + len(residuales_audio)
        pasos_ok.append(
            f"Hay {total_res} track(s) de una corrida anterior; se van a "
            "limpiar automaticamente antes de generar (no te preocupes)."
        )

    return Diagnostico(
        nivel="ok",
        titulo="Todo listo para generar.",
        pasos=pasos_ok,
        puede_continuar=True,
    )


def interpretar_error(exc: Exception) -> Diagnostico:
    """Convierte una excepcion tecnica en un mensaje accionable.

    No intenta cubrir todo: traduce los errores conocidos y para el resto
    da un mensaje generico pero util (con el texto tecnico al final por si
    hace falta investigar).
    """
    texto = str(exc)
    tipo = type(exc).__name__

    # Archivo no encontrado / ruta mal
    if isinstance(exc, FileNotFoundError) or "No es un archivo" in texto:
        return Diagnostico(
            nivel="error",
            titulo="No se encontro el archivo del proyecto.",
            pasos=[
                "El draft_content.json no existe en la ruta indicada.",
                "Volve a elegir el proyecto de la lista, o verifica que el",
                "proyecto siga existiendo en CapCut.",
            ],
            puede_continuar=False,
        )

    # JSON corrupto / estructura invalida
    if "JSON" in texto or "draft de CapCut" in texto or tipo == "InvalidDraftError":
        return Diagnostico(
            nivel="error",
            titulo="El archivo del proyecto esta dañado o incompleto.",
            pasos=[
                "El draft_content.json no se pudo leer como un proyecto valido.",
                "Abri el proyecto en CapCut, guardalo de nuevo (Ctrl+S),",
                "cerra CapCut y volve a intentar.",
                "Si sigue fallando, puede que el proyecto este corrupto en CapCut.",
            ],
            puede_continuar=False,
        )

    # Archivo demasiado grande
    if "demasiado grande" in texto:
        return Diagnostico(
            nivel="error",
            titulo="El archivo del proyecto es demasiado grande.",
            pasos=[texto],
            puede_continuar=False,
        )

    # Generico
    return Diagnostico(
        nivel="error",
        titulo="Ocurrio un error inesperado.",
        pasos=[
            "No se pudo completar la operacion.",
            f"Detalle tecnico: {tipo}: {texto}",
            "Si el problema persiste, usa el boton 'Diagnosticar' para",
            "ver el estado interno del proyecto.",
        ],
        puede_continuar=False,
    )


def aviso_capcut_abierto(esta_corriendo: Optional[bool]) -> Optional[Diagnostico]:
    """Devuelve un Diagnostico de aviso si CapCut esta (o podria estar)
    abierto. Devuelve None si es seguro continuar.

    Args:
        esta_corriendo: True / False / None (no se sabe), tal como lo
                        devuelve capcut_projects.capcut_esta_corriendo().
    """
    if esta_corriendo is True:
        return Diagnostico(
            nivel="error",
            titulo="CapCut esta ABIERTO ahora mismo.",
            pasos=[
                "Si genero los subtitulos con CapCut abierto, al cerrarse",
                "CapCut va a SOBREESCRIBIR el resultado y se pierde todo.",
                "",
                "1. Cerra CapCut por completo.",
                "2. Verifica en el Administrador de Tareas que no quede",
                "   ningun proceso 'CapCut' corriendo.",
                "3. Volve a intentar.",
            ],
            puede_continuar=False,
        )
    if esta_corriendo is None:
        return Diagnostico(
            nivel="aviso",
            titulo="No se pudo verificar si CapCut esta cerrado.",
            pasos=[
                "Por las dudas, asegurate vos mismo de que CapCut este",
                "completamente cerrado antes de generar (incluido cualquier",
                "proceso en segundo plano en el Administrador de Tareas).",
            ],
            puede_continuar=True,
        )
    return None

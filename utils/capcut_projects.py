"""
Utilidades para descubrir y listar los proyectos (drafts) de CapCut
directamente desde el sistema de archivos, sin depender de pycapcut.

Por que NO se usa pycapcut aca: pycapcut puede fallar al leer ciertos
drafts (ej. el KeyError 'fps' documentado en el handoff original) y eso
tiraria abajo TODO el listado de proyectos solo porque uno esta corrupto.
Leyendo el filesystem directamente, un draft problematico no impide ver
ni elegir los demas.

Estructura real en disco (Windows):
  C:\\Users\\<USER>\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft\\
      <nombre del proyecto>\\
          draft_content.json   <- el archivo que el sistema procesa
          draft_meta_info.json
          ...
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


# Rutas tipicas de la carpeta de drafts de CapCut por sistema operativo.
# Se prueban en orden; la primera que exista gana. Cubre CapCut global y
# CapCut chino (JianYing), que algunos usuarios tienen.
_CANDIDATE_SUBPATHS = [
    r"AppData\Local\CapCut\User Data\Projects\com.lveditor.draft",
    r"AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft",
    # macOS
    "Movies/CapCut/User Data/Projects/com.lveditor.draft",
    "Library/Application Support/CapCut/User Data/Projects/com.lveditor.draft",
]

# Nombres de proceso de CapCut por plataforma (para detectar si esta abierto).
_CAPCUT_PROCESS_NAMES = ["capcut", "jianyingpro", "jianying"]


@dataclass
class CapcutProject:
    """Un proyecto de CapCut encontrado en disco."""
    name: str
    folder: Path
    draft_json: Path
    modified_ts: float  # timestamp de ultima modificacion (para ordenar)

    @property
    def modified_human(self) -> str:
        from datetime import datetime
        return datetime.fromtimestamp(self.modified_ts).strftime("%Y-%m-%d %H:%M")


def encontrar_carpeta_drafts(ruta_manual: Optional[str] = None) -> Optional[Path]:
    """Devuelve la carpeta de drafts de CapCut, o None si no se encuentra.

    Args:
        ruta_manual: si se provee y existe, se usa esa (tiene prioridad).
                     Permite que un usuario con una instalacion no estandar
                     configure la ruta a mano (ej. en settings.json).
    """
    if ruta_manual:
        p = Path(ruta_manual)
        if p.is_dir():
            return p

    home = Path(os.path.expanduser("~"))
    for sub in _CANDIDATE_SUBPATHS:
        p = home / sub
        if p.is_dir():
            return p
    return None


def listar_proyectos(
    ruta_manual: Optional[str] = None,
    solo_con_json: bool = True,
) -> List[CapcutProject]:
    """Lista los proyectos de CapCut ordenados por fecha de modificacion
    (el mas reciente primero -- normalmente el que el usuario quiere).

    Args:
        ruta_manual: ruta a la carpeta de drafts (opcional, ver
                     encontrar_carpeta_drafts).
        solo_con_json: si True (default), omite carpetas que no tengan un
                       draft_content.json adentro (carpetas de sistema,
                       templates vacios, etc).

    Returns:
        Lista de CapcutProject. Vacia si no se encuentra la carpeta o no
        hay proyectos.
    """
    carpeta = encontrar_carpeta_drafts(ruta_manual)
    if carpeta is None:
        return []

    proyectos: List[CapcutProject] = []
    try:
        entradas = list(carpeta.iterdir())
    except OSError:
        return []

    for entry in entradas:
        if not entry.is_dir():
            continue
        # CapCut usa algunas carpetas internas que empiezan con punto o son
        # de sistema; las omitimos.
        if entry.name.startswith("."):
            continue

        draft_json = entry / "draft_content.json"
        if solo_con_json and not draft_json.is_file():
            continue

        try:
            # Preferimos la fecha del draft_content.json (refleja la ultima
            # edicion real del contenido); si no existe, la de la carpeta.
            if draft_json.is_file():
                ts = draft_json.stat().st_mtime
            else:
                ts = entry.stat().st_mtime
        except OSError:
            ts = 0.0

        proyectos.append(
            CapcutProject(
                name=entry.name,
                folder=entry,
                draft_json=draft_json,
                modified_ts=ts,
            )
        )

    proyectos.sort(key=lambda p: p.modified_ts, reverse=True)
    return proyectos


def capcut_esta_corriendo() -> Optional[bool]:
    """Indica si hay un proceso de CapCut corriendo ahora mismo.

    Returns:
        True  -> CapCut esta abierto (NO se debe escribir el draft).
        False -> CapCut no esta corriendo (seguro escribir).
        None  -> no se pudo determinar (psutil no instalado / SO no
                 soportado). El llamador deberia tratar None como
                 "no se sabe, avisar al usuario por las dudas".

    Detectar esto evita el bug mas costoso del proyecto: si CapCut esta
    abierto mientras el script escribe draft_content.json, al cerrarse
    CapCut SOBREESCRIBE el archivo con su version en memoria, destruyendo
    todo el trabajo generado (documentado en el handoff).
    """
    try:
        import psutil
    except ImportError:
        # Fallback sin psutil: intentar con herramientas del sistema.
        return _capcut_corriendo_sin_psutil()

    try:
        for proc in psutil.process_iter(["name"]):
            nombre = (proc.info.get("name") or "").lower()
            if any(cc in nombre for cc in _CAPCUT_PROCESS_NAMES):
                return True
        return False
    except Exception:
        return None


def _capcut_corriendo_sin_psutil() -> Optional[bool]:
    """Deteccion de CapCut sin psutil, usando comandos del sistema.

    En Windows usa 'tasklist'. En otros SO devuelve None (no se sabe) para
    no dar un falso negativo que lleve al usuario a sobreescribir su draft.
    """
    import subprocess
    import sys

    if not sys.platform.startswith("win"):
        return None

    try:
        salida = subprocess.run(
            ["tasklist"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return None

    return any(cc in salida for cc in _CAPCUT_PROCESS_NAMES)

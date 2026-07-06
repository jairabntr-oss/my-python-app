"""
Divide un draft de CapCut en N proyectos independientes, cada uno
recortado a un rango de tiempo, con texto/auto-caption filtrado y
reubicado en 0. El archivo de video/audio FUENTE no se copia ni se
modifica: el draft nuevo sigue apuntando al mismo archivo por su ruta
absoluta, CapCut lo recorta visualmente segun el rango.

Generalizacion de un script real (cortar_4_clips.py) que ya se uso para
partir una entrevista en 4 clips independientes.
"""

import copy
import json
import shutil
from pathlib import Path
from typing import List, Tuple


def _recortar_segmento_video(seg: dict, inicio_us: int, fin_us: int) -> dict:
    """target_timerange arranca en 0; source_timerange se desplaza para
    tomar el tramo correcto del archivo fuente original."""
    nuevo = copy.deepcopy(seg)
    dur = fin_us - inicio_us
    src = nuevo["source_timerange"]
    nuevo["source_timerange"] = {"start": src["start"] + inicio_us, "duration": dur}
    nuevo["target_timerange"] = {"start": 0, "duration": dur}
    return nuevo


def _filtrar_y_desplazar_texto(segments: List[dict], inicio_us: int, fin_us: int) -> List[dict]:
    """Solo los segmentos de texto que caen COMPLETAMENTE dentro del
    rango (no se recortan a la mitad, para no truncar palabras): se
    descartan enteros los que empiezan antes o terminan despues."""
    resultado = []
    for seg in segments:
        tr = seg["target_timerange"]
        s_ini, s_fin = tr["start"], tr["start"] + tr["duration"]
        if s_ini >= inicio_us and s_fin <= fin_us:
            nuevo = copy.deepcopy(seg)
            nuevo["target_timerange"] = {"start": s_ini - inicio_us, "duration": tr["duration"]}
            resultado.append(nuevo)
    return resultado


def construir_clip(data_original: dict, inicio_us: int, fin_us: int) -> Tuple[dict, int]:
    """Devuelve (draft_recortado, cantidad_de_segmentos_de_texto)."""
    if fin_us > int(data_original.get("duration", 0)):
        raise ValueError(
            f"el rango termina en {fin_us/1e6:.2f}s pero el draft original "
            f"dura solo {data_original.get('duration', 0)/1e6:.2f}s")

    data = copy.deepcopy(data_original)
    tracks_nuevos = []
    ids_texto_usados = set()

    for track in data["tracks"]:
        if track["type"] == "video" and track.get("segments"):
            track["segments"] = [
                _recortar_segmento_video(track["segments"][0], inicio_us, fin_us)
            ]
            tracks_nuevos.append(track)
        elif track["type"] == "text":
            track["segments"] = _filtrar_y_desplazar_texto(
                track.get("segments", []), inicio_us, fin_us)
            for s in track["segments"]:
                ids_texto_usados.add(s["material_id"])
            tracks_nuevos.append(track)
        else:
            tracks_nuevos.append(track)

    data["tracks"] = tracks_nuevos
    data["duration"] = fin_us - inicio_us

    if "materials" in data and "texts" in data["materials"]:
        data["materials"]["texts"] = [
            m for m in data["materials"]["texts"] if m["id"] in ids_texto_usados
        ]

    return data, len(ids_texto_usados)


def crear_proyecto_nuevo(
    carpeta_drafts: Path, nombre_original: str, sufijo: str, draft_data: dict,
) -> Path:
    """Copia la carpeta completa del proyecto original (asi CapCut tiene
    todos los archivos auxiliares que necesita) y le reemplaza el
    draft_content.json por el recortado."""
    origen = carpeta_drafts / nombre_original
    destino = carpeta_drafts / f"{nombre_original} - {sufijo}"

    if destino.exists():
        raise FileExistsError(
            f"ya existe una carpeta de proyecto en {destino}. Borrala o "
            "renombrala en CapCut si queres regenerarla.")
    if not origen.exists():
        raise FileNotFoundError(f"no encontre la carpeta original en {origen}")

    shutil.copytree(origen, destino)

    (destino / "draft_content.json").write_text(
        json.dumps(draft_data, ensure_ascii=False), encoding="utf-8")

    meta_path = destino / "draft_meta_info.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if "draft_name" in meta:
                meta["draft_name"] = f"{nombre_original} - {sufijo}"
            meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # no bloqueante: CapCut igual reconoce el proyecto por carpeta

    return destino


def parsear_rangos(texto_rangos: str) -> List[Tuple[str, float, float]]:
    """Parsea "0:00-1:05,1:14-1:46,2:00-2:38" o "0-65,74-106" (segundos)
    a [(sufijo, inicio_seg, fin_seg), ...]. El sufijo es "parteN"."""
    def a_segundos(token: str) -> float:
        token = token.strip()
        if ":" in token:
            m, s = token.split(":")
            return int(m) * 60 + float(s)
        return float(token)

    rangos = []
    for i, par in enumerate(texto_rangos.split(","), start=1):
        ini_s, fin_s = par.split("-")
        rangos.append((f"parte{i}", a_segundos(ini_s), a_segundos(fin_s)))
    return rangos

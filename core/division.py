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


def construir_resumen(data_original: dict, rangos: List[Tuple[int, int]]) -> Tuple[dict, int]:
    """Arma UN video continuo tomando varios rangos SALTEADOS del
    original y pegandolos uno detras del otro, en el orden dado.

    A diferencia de construir_clip (un solo rango -> un solo clip),
    esto es un "resumen"/highlight: cada rango puede caer sobre uno o
    varios segmentos de video YA EXISTENTES (el material real suele
    tener cortes previos - zooms, color grading), asi que cada rango
    se recorta igual que hace core.velocidad._partir_y_acelerar, pero
    en vez de acelerar la porcion elegida, se la CONSERVA a velocidad
    normal y se descarta todo lo que quedo afuera de los rangos.

    Devuelve (draft_resumen, cantidad_de_segmentos_de_texto).
    """
    data = copy.deepcopy(data_original)
    duracion_total_original = int(data_original.get("duration", 0))

    for p1, p2 in rangos:
        if p1 < 0 or p2 > duracion_total_original or p1 >= p2:
            raise ValueError(
                f"rango invalido {p1/1e6:.2f}s-{p2/1e6:.2f}s (el original "
                f"dura {duracion_total_original/1e6:.2f}s)")

    tracks_nuevos = []
    ids_texto_usados = set()
    cursor_target = 0
    duracion_resumen = 0

    for track in data["tracks"]:
        if track["type"] == "video":
            piezas_track = []
            cursor = 0  # se recalcula por rango, ver abajo
            for p1, p2 in rangos:
                for seg in track.get("segments", []):
                    t = seg.get("target_timerange") or {}
                    t_ini, t_dur = int(t.get("start", 0)), int(t.get("duration", 0))
                    t_fin = t_ini + t_dur
                    ini_local = max(t_ini, p1)
                    fin_local = min(t_fin, p2)
                    dur_dentro = fin_local - ini_local
                    if dur_dentro <= 0:
                        continue  # este segmento no toca este rango

                    s = seg["source_timerange"]
                    s_ini = int(s["start"])
                    offset_dentro = ini_local - t_ini

                    pieza = copy.deepcopy(seg)
                    pieza["id"] = _nuevo_id_local()
                    pieza["target_timerange"] = {"start": cursor, "duration": dur_dentro}
                    pieza["source_timerange"] = {
                        "start": s_ini + offset_dentro, "duration": dur_dentro}
                    piezas_track.append(pieza)
                    cursor += dur_dentro
            track["segments"] = piezas_track
            tracks_nuevos.append(track)
            duracion_resumen = max(duracion_resumen, cursor)

        elif track["type"] == "text":
            piezas_texto = []
            cursor_texto = 0
            for p1, p2 in rangos:
                offset_rango = cursor_texto
                for seg in track.get("segments", []):
                    t = seg["target_timerange"]
                    s_ini_seg, s_fin_seg = t["start"], t["start"] + t["duration"]
                    if s_ini_seg >= p1 and s_fin_seg <= p2:
                        nuevo = copy.deepcopy(seg)
                        nuevo["target_timerange"] = {
                            "start": (s_ini_seg - p1) + offset_rango,
                            "duration": t["duration"],
                        }
                        piezas_texto.append(nuevo)
                        ids_texto_usados.add(seg["material_id"])
                cursor_texto = offset_rango + (p2 - p1)
            track["segments"] = piezas_texto
            tracks_nuevos.append(track)
        else:
            track["segments"] = []  # audio-narracion aparte, tracks vacios de otro tipo se descartan
            tracks_nuevos.append(track)

    data["tracks"] = tracks_nuevos
    data["duration"] = duracion_resumen

    if "materials" in data and "texts" in data["materials"]:
        data["materials"]["texts"] = [
            m for m in data["materials"]["texts"] if m["id"] in ids_texto_usados
        ]

    return data, len(ids_texto_usados)


def _nuevo_id_local() -> str:
    import uuid
    return str(uuid.uuid4()).upper()


def parsear_rangos_resumen(texto_rangos: str) -> List[Tuple[int, int]]:
    """Parsea "0:26-0:29,0:52-1:03" (mm:ss) a [(inicio_us, fin_us), ...]
    en el ORDEN dado (asi se controla el orden final del resumen)."""
    def a_us(token: str) -> int:
        token = token.strip()
        if ":" in token:
            m, s = token.split(":")
            return int((int(m) * 60 + float(s)) * 1e6)
        return int(float(token) * 1e6)

    rangos = []
    for par in texto_rangos.split(","):
        ini_s, fin_s = par.split("-")
        rangos.append((a_us(ini_s), a_us(fin_s)))
    return rangos


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

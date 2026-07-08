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


def _extraer_rango_robusto(data_original: dict, p1: int, p2: int) -> dict:
    """Extrae [p1,p2) a un mini-draft 0-based, soportando que el video ya
    tenga varios segmentos preexistentes dentro del rango (mismo criterio
    que construir_resumen). No modifica data_original."""
    tracks_out = []
    ids_texto_usados = set()

    for track in data_original["tracks"]:
        base = {k: v for k, v in track.items() if k != "segments"}
        if track["type"] == "video":
            piezas = []
            cursor = 0
            for seg in track.get("segments", []):
                t = seg.get("target_timerange") or {}
                t_ini, t_dur = int(t.get("start", 0)), int(t.get("duration", 0))
                t_fin = t_ini + t_dur
                ini_local, fin_local = max(t_ini, p1), min(t_fin, p2)
                dur_dentro = fin_local - ini_local
                if dur_dentro <= 0:
                    continue
                s = seg["source_timerange"]
                s_ini = int(s["start"])
                offset_dentro = ini_local - t_ini
                pieza = copy.deepcopy(seg)
                pieza["id"] = _nuevo_id_local()
                pieza["target_timerange"] = {"start": cursor, "duration": dur_dentro}
                pieza["source_timerange"] = {
                    "start": s_ini + offset_dentro, "duration": dur_dentro}
                piezas.append(pieza)
                cursor += dur_dentro
            tracks_out.append({**copy.deepcopy(base), "segments": piezas})
        elif track["type"] == "text":
            piezas = []
            for seg in track.get("segments", []):
                t = seg["target_timerange"]
                s_ini_seg, s_fin_seg = t["start"], t["start"] + t["duration"]
                if s_ini_seg >= p1 and s_fin_seg <= p2:
                    nuevo = copy.deepcopy(seg)
                    nuevo["target_timerange"] = {
                        "start": s_ini_seg - p1, "duration": t["duration"]}
                    piezas.append(nuevo)
                    ids_texto_usados.add(seg["material_id"])
            tracks_out.append({**copy.deepcopy(base), "segments": piezas})
        else:
            tracks_out.append({**copy.deepcopy(base), "segments": []})

    materials = copy.deepcopy(data_original.get("materials", {}))
    if "texts" in materials:
        materials["texts"] = [m for m in materials["texts"] if m["id"] in ids_texto_usados]

    return {"duration": p2 - p1, "tracks": tracks_out, "materials": materials}


def construir_resumen_mixto(
    data_original: dict, oraciones_completas: List[List[dict]],
    especificaciones: List[dict],
) -> Tuple[dict, int]:
    """Como construir_resumen, pero cada tramo puede ser:
      {"tipo": "cortar", "inicio": us, "fin": us}
        -> se extrae tal cual, sin tocar velocidad.
      {"tipo": "acelerar", "inicio": us, "fin": us,
       "velocidad_min": float, "velocidad_max": float, "min_silencio": float}
        -> se CONSERVA todo el contenido hablado de ese tramo (no se
        corta ninguna frase), pero se comprimen los SILENCIOS dentro de
        el con el mismo criterio que el comando 'acelerar' independiente
        (mas tiempo a pausas tras frases densas, corte fuerte a pausas
        tras frases cortas).

    oraciones_completas: las oraciones del draft ORIGINAL completo (el
    mismo formato que devuelve engine.extract_captions_from_draft),
    usadas para calcular pausas/velocidad solo dentro de cada tramo
    "acelerar" (se filtran y se re-basan a 0 automaticamente).
    """
    import json as _json
    import os
    import tempfile

    from core.velocidad import AceleradorPausas, calcular_velocidad_por_importancia
    from utils.analisis_video import detectar_pausas_habla

    duracion_total_original = int(data_original.get("duration", 0))
    for spec in especificaciones:
        p1, p2 = spec["inicio"], spec["fin"]
        if p1 < 0 or p2 > duracion_total_original or p1 >= p2:
            raise ValueError(
                f"rango invalido {p1/1e6:.2f}s-{p2/1e6:.2f}s (el original "
                f"dura {duracion_total_original/1e6:.2f}s)")

    video_final, texto_final = [], []
    ids_texto_usados = set()
    cursor = 0

    for spec in especificaciones:
        p1, p2 = spec["inicio"], spec["fin"]
        mini = _extraer_rango_robusto(data_original, p1, p2)

        if spec["tipo"] == "acelerar":
            oraciones_rango = []
            for o in oraciones_completas:
                if o and o[0]["start_us"] >= p1 and o[-1]["end_us"] <= p2:
                    oraciones_rango.append([
                        {**w, "start_us": w["start_us"] - p1, "end_us": w["end_us"] - p1}
                        for w in o
                    ])

            pausas = detectar_pausas_habla(
                oraciones_rango, min_pausa_seg=spec.get("min_silencio", 1.0),
                duracion_video_seg=(p2 - p1) / 1e6)
            pausas_vel = calcular_velocidad_por_importancia(
                pausas, oraciones_rango,
                spec.get("velocidad_min", 2.0), spec.get("velocidad_max", 8.0))

            fd, temp_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            try:
                with open(temp_path, "w", encoding="utf-8") as f:
                    _json.dump(mini, f)
                ac = AceleradorPausas(temp_path)
                if pausas_vel:
                    ac.acelerar_pausas(pausas_vel)
                mini_final = ac.data
            finally:
                os.unlink(temp_path)
        else:
            mini_final = mini

        for track in mini_final["tracks"]:
            if track["type"] == "video":
                for seg in track.get("segments", []):
                    seg["target_timerange"]["start"] += cursor
                    video_final.append(seg)
            elif track["type"] == "text":
                for seg in track.get("segments", []):
                    seg["target_timerange"]["start"] += cursor
                    texto_final.append(seg)
                    ids_texto_usados.add(seg["material_id"])

        cursor += int(mini_final["duration"])

    data = copy.deepcopy(data_original)
    tracks_nuevos = []
    video_asignado = texto_asignado = False
    for track in data["tracks"]:
        if track["type"] == "video" and not video_asignado:
            track["segments"] = video_final
            tracks_nuevos.append(track)
            video_asignado = True
        elif track["type"] == "text" and not texto_asignado:
            track["segments"] = texto_final
            tracks_nuevos.append(track)
            texto_asignado = True
        elif track["type"] in ("video", "text"):
            continue
        else:
            track["segments"] = []
            tracks_nuevos.append(track)

    data["tracks"] = tracks_nuevos
    data["duration"] = cursor

    if "materials" in data and "texts" in data["materials"]:
        data["materials"]["texts"] = [
            m for m in data["materials"]["texts"] if m["id"] in ids_texto_usados
        ]

    return data, len(ids_texto_usados)


def parsear_especificaciones_mixtas(texto: str) -> List[dict]:
    """Parsea "acelerar:0:00-1:36.26,cortar:2:19.13-2:34.27,..." a una
    lista de specs para construir_resumen_mixto. Si un rango no trae
    prefijo, se asume "cortar" (compatibilidad con formato simple)."""
    def a_us(token: str) -> int:
        token = token.strip()
        if ":" in token:
            m, s = token.split(":")
            return int((int(m) * 60 + float(s)) * 1e6)
        return int(float(token) * 1e6)

    specs = []
    for parte in texto.split(","):
        parte = parte.strip()
        tipo, _, resto = parte.partition(":")
        if tipo not in ("acelerar", "cortar"):
            tipo, resto = "cortar", parte
        ini_s, fin_s = resto.split("-")
        specs.append({"tipo": tipo, "inicio": a_us(ini_s), "fin": a_us(fin_s)})
    return specs


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

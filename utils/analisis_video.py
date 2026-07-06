"""
Analisis de video con ffmpeg puro (sin IA): silencios, cambios de escena,
y localizacion del archivo de video a partir del draft de CapCut.

Requiere ffmpeg instalado y en el PATH.
En Windows: winget install Gyan.FFmpeg   (y reabrir la consola)
"""

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional


def ffmpeg_disponible() -> bool:
    return shutil.which("ffmpeg") is not None


def video_desde_draft(draft_json: Path) -> Optional[Path]:
    """Encuentra el archivo de video principal del draft.

    Lee materials.videos del draft_content.json y devuelve el video de
    mayor duracion (el clip principal de la entrevista, no B-rolls cortos).
    """
    with open(draft_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    videos = (data.get("materials") or {}).get("videos") or []
    candidatos = []
    for v in videos:
        # En CapCut los materiales de imagen tambien viven en "videos";
        # filtramos por tipo y por path existente.
        if v.get("type") not in (None, "video"):
            continue
        path = v.get("path") or ""
        # CapCut a veces guarda placeholders tipo "##_draftpath_##/..."
        if "##" in path:
            path = path.replace(
                "##_draftpath_##", str(draft_json.parent)
            )
        p = Path(path)
        if p.is_file():
            candidatos.append((int(v.get("duration", 0) or 0), p))

    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    return candidatos[0][1]


def detectar_silencios(
    video: Path, umbral_db: int = -35, min_duracion_seg: float = 1.0
) -> List[dict]:
    """Silencios de al menos min_duracion_seg segundos, via silencedetect."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(video),
        "-af", f"silencedetect=noise={umbral_db}dB:d={min_duracion_seg}",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)

    silencios = []
    inicio = None
    for linea in res.stderr.splitlines():
        m = re.search(r"silence_start:\s*([\d.]+)", linea)
        if m:
            inicio = float(m.group(1))
            continue
        m = re.search(r"silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)", linea)
        if m and inicio is not None:
            silencios.append({
                "inicio": inicio,
                "fin": float(m.group(1)),
                "duracion": float(m.group(2)),
            })
            inicio = None
    return silencios


def detectar_cambios_escena(video: Path, umbral: float = 0.35) -> List[float]:
    """Timestamps (seg) donde el contenido visual cambia bruscamente."""
    cmd = [
        "ffmpeg", "-hide_banner", "-i", str(video),
        "-vf", f"select='gt(scene,{umbral})',metadata=print",
        "-an", "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)

    cambios = []
    for linea in res.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", linea)
        if m:
            cambios.append(float(m.group(1)))
    return cambios


def detectar_pausas_habla(
    oraciones: List[List[dict]],
    min_pausa_seg: float = 0.8,
    duracion_video_seg: float = 0.0,
) -> List[dict]:
    """Pausas en el HABLA usando los timestamps del auto-caption.

    Inmune al ruido ambiente (concesionaria, motor, viento): no mira el
    nivel de audio, mira cuando NADIE esta diciendo una palabra segun el
    reconocimiento de voz de CapCut.

    Maneja dialogo superpuesto: recorre todas las palabras de todas las
    oraciones ordenadas por inicio y solo cuenta pausa cuando el hueco
    supera el fin de TODO lo dicho hasta ahi (asi dos personas hablando
    a la vez no generan pausas falsas).

    oraciones: List[List[{word,start_us,end_us}]] (formato del repo).
    duracion_video_seg: si se pasa, tambien reporta el aire muerto
    inicial (antes de la primera palabra) y final (despues de la ultima).
    """
    palabras = sorted(
        (w["start_us"] / 1e6, w["end_us"] / 1e6)
        for o in oraciones for w in o
    )
    if not palabras:
        return []

    pausas = []

    # Aire muerto inicial
    if palabras[0][0] >= min_pausa_seg:
        pausas.append({
            "inicio": 0.0, "fin": palabras[0][0],
            "duracion": palabras[0][0], "tipo": "inicio_video",
        })

    fin_actual = palabras[0][1]
    for ini, fin in palabras[1:]:
        hueco = ini - fin_actual
        if hueco >= min_pausa_seg:
            pausas.append({
                "inicio": fin_actual, "fin": ini,
                "duracion": hueco, "tipo": "entre_frases",
            })
        fin_actual = max(fin_actual, fin)

    # Aire muerto final
    if duracion_video_seg and duracion_video_seg - fin_actual >= min_pausa_seg:
        pausas.append({
            "inicio": fin_actual, "fin": duracion_video_seg,
            "duracion": duracion_video_seg - fin_actual, "tipo": "fin_video",
        })

    return pausas


def construir_bloques_desde_subtitulos(draft_json_path) -> list:
    """Reconstruye "oraciones" (formato que espera ClickEngine.generate)
    a partir de los segmentos de texto YA EXISTENTES en el draft, para
    cuando el auto-caption original ya no esta disponible (el usuario
    ya recorto y/o edito los subtitulos a mano).

    Agrupa por BLOQUE VISUAL real: un bloque nuevo arranca cuando una
    palabra empieza en o despues del momento en que el bloque anterior
    deja de mostrarse en pantalla (no intenta adivinar oraciones
    gramaticales por pausas, que da cortes erraticos en texto ya
    editado a mano).
    """
    import json as _json
    with open(draft_json_path, "r", encoding="utf-8") as f:
        data = _json.load(f)

    texts_by_id = {t["id"]: t for t in data.get("materials", {}).get("texts", [])}
    palabras = []
    for track in data.get("tracks", []):
        if track.get("type") != "text":
            continue
        for seg in track.get("segments", []):
            mat = texts_by_id.get(seg.get("material_id"))
            if mat is None:
                continue
            try:
                content = _json.loads(mat["content"])
            except Exception:
                continue
            texto = (content.get("text") or "").strip()
            if not texto:
                continue
            tr = seg["target_timerange"]
            palabras.append({
                "word": texto,
                "start_us": tr["start"],
                "end_us": tr["start"] + tr["duration"],
            })

    palabras.sort(key=lambda p: p["start_us"])

    bloques, bloque_actual, fin_max = [], [], None
    for p in palabras:
        if fin_max is not None and p["start_us"] >= fin_max:
            bloques.append(bloque_actual)
            bloque_actual = []
            fin_max = None
        bloque_actual.append(p)
        fin_max = p["end_us"] if fin_max is None else max(fin_max, p["end_us"])
    if bloque_actual:
        bloques.append(bloque_actual)
    return bloques


def clasificar_silencios(
    silencios: List[dict],
    oraciones: List[List[dict]],
    margen_seg: float = 0.15,
) -> List[dict]:
    """Marca cada silencio como corte 'seguro' o 'riesgoso'.

    Seguro = el silencio NO se superpone con ninguna oracion del
    auto-caption (cae entre frases). Riesgoso = pisa una oracion
    (probablemente una pausa dramatica a mitad de idea, o ruido de
    timestamps del reconocimiento de voz).

    oraciones: List[List[{word,start_us,end_us}]] (formato del repo).
    margen_seg: tolerancia para el ruido de timestamps del auto-caption
    (el mismo problema del umbral de overlap del handoff, Error #9).
    """
    rangos = []
    for o in oraciones:
        if o:
            rangos.append((o[0]["start_us"] / 1e6, o[-1]["end_us"] / 1e6))

    resultado = []
    for s in silencios:
        ini = s["inicio"] + margen_seg
        fin = s["fin"] - margen_seg
        pisa_oracion = any(
            ini < r_fin and fin > r_ini for (r_ini, r_fin) in rangos
        )
        resultado.append({**s, "seguro": not pisa_oracion})
    return resultado

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

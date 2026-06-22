"""
Extractor unificado y robusto del auto-caption de un draft de CapCut.

Antes habia 3 parsers distintos y en conflicto (este, draft_manager y
capcut_parser), cada uno asumiendo una estructura/unidad diferente. Eso hacia
que segun la version de CapCut no extrajera nada, o sacara tiempos 1000x mal.

Ahora hay UNA sola fuente de verdad:
  1) Se intenta DraftManager (lee content como JSON string, words[] en microseg,
     y filtra solo el auto-caption SIN editar). Es el camino probado con datos
     reales.
  2) Si eso no devuelve nada (otra version de CapCut), respaldo: lee
     materials.texts[].words como arrays paralelos (text/start_time/end_time) y
     DETECTA la unidad de tiempo (us/ms/s) comparando contra la duracion del
     draft, en vez de asumir milisegundos a ciegas.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple

from core.draft_manager import DraftManager


class AutocaptionExtractor:
    """Extrae auto-caption del draft de CapCut (robusto a varias versiones)."""

    @staticmethod
    def extract(json_path: str) -> Tuple[List[List[Dict]], Dict]:
        """Extrae oraciones con palabras y timings en microsegundos.

        Returns:
            (oraciones, stats)
        """
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                draft = json.load(f)
        except Exception as e:
            return [], {"error": f"Error leyendo JSON: {e}"}

        materials_texts = draft.get("materials", {}).get("texts", []) or []
        stats = {
            "total_materials": len(materials_texts),
            "materiales_con_words": 0,
            "oraciones_extraidas": 0,
            "metodo": None,
        }

        # ── Camino 1: DraftManager (probado con datos reales) ──────────────
        try:
            oraciones, _ = DraftManager.oraciones_desde_json(json_path)
        except Exception:
            oraciones = []

        if oraciones:
            stats["metodo"] = "draft_manager (content/microsegundos)"
            stats["materiales_con_words"] = len(oraciones)
            stats["oraciones_extraidas"] = len(oraciones)
            return oraciones, stats

        # ── Camino 2: respaldo arrays paralelos con deteccion de unidad ────
        oraciones = AutocaptionExtractor._extraer_por_arrays(materials_texts, draft, stats)
        stats["metodo"] = "arrays paralelos (respaldo)"
        stats["oraciones_extraidas"] = len(oraciones)
        return oraciones, stats

    # ------------------------------------------------------------------
    @staticmethod
    def _offsets_por_material(draft) -> Dict[str, int]:
        """Mapea material_id -> inicio absoluto (en las unidades crudas del
        propio draft) de su segmento en el track de texto.

        CRITICO: los arrays start_time/end_time dentro de 'words' son
        RELATIVOS al inicio de cada linea/oracion, no al timeline absoluto
        del video. Sin sumar este offset, todas las oraciones quedarian
        ancladas a 0.00s (bug detectado con un draft real).
        """
        offsets = {}
        for track in draft.get("tracks", []) or []:
            if track.get("type") != "text":
                continue
            for seg in track.get("segments", []) or []:
                mid = seg.get("material_id")
                tr = seg.get("target_timerange", {}) or {}
                start = tr.get("start")
                if mid is not None and start is not None:
                    offsets[mid] = int(start)
        return offsets

    # ------------------------------------------------------------------
    @staticmethod
    def _detectar_multiplicador(median_dur_raw: int, max_raw: int, duration_us: int) -> int:
        """Factor para llevar timings crudos a microsegundos.

        Desambigua us/ms/s usando la duracion TIPICA de una palabra hablada
        (~0.3s). Una palabra cruda de 400 unidades son 0.0004s si fueran us
        (absurdo) o 0.4s si fueran ms (real) -> elige ms.
        """
        candidatos = (1, 1000, 1_000_000)
        TARGET_US = 300_000  # duracion plausible de una palabra (~0.3s)
        if median_dur_raw and median_dur_raw > 0:
            return min(candidatos, key=lambda m: abs(median_dur_raw * m - TARGET_US))
        # respaldo: por magnitud del maximo vs duracion del video
        if duration_us and duration_us > 0 and max_raw > 0:
            for mult in candidatos:
                if max_raw * mult <= duration_us * 1.5:
                    return mult
        if max_raw > 10_000_000:
            return 1
        return 1000

    @staticmethod
    def _extraer_por_arrays(materials_texts, draft, stats) -> List[List[Dict]]:
        duration_us = int(draft.get("duration", 0) or 0)
        offsets = AutocaptionExtractor._offsets_por_material(draft)

        # relevar maximo crudo y duraciones de palabra para detectar la unidad
        max_raw = 0
        duraciones = []
        for material in materials_texts:
            wd = material.get("words", {})
            if not isinstance(wd, dict):
                continue
            starts = wd.get("start_time", []) or []
            ends = wd.get("end_time", []) or []
            for v in ends or starts:
                try:
                    max_raw = max(max_raw, int(v))
                except (TypeError, ValueError):
                    pass
            for a, b in zip(starts, ends):
                try:
                    d = int(b) - int(a)
                    if d > 0:
                        duraciones.append(d)
                except (TypeError, ValueError):
                    pass
        median_dur = 0
        if duraciones:
            duraciones.sort()
            median_dur = duraciones[len(duraciones) // 2]
        mult = AutocaptionExtractor._detectar_multiplicador(median_dur, max_raw, duration_us)

        oraciones = []
        for material in materials_texts:
            wd = material.get("words", {})
            if not isinstance(wd, dict) or not wd:
                continue
            stats["materiales_con_words"] += 1
            # offset absoluto del segmento (en microsegundos, ya escalado);
            # si no se encontro el segmento (material huerfano), offset=0
            offset_us = offsets.get(material.get("id"), 0)
            oracion = AutocaptionExtractor._extraer_oracion(wd, mult, offset_us)
            if oracion:
                oraciones.append(oracion)
        # ordenar por tiempo de inicio real: los materiales no necesariamente
        # vienen en orden cronologico dentro de materials.texts
        oraciones.sort(key=lambda o: o[0]["start_us"])
        return oraciones

    @staticmethod
    def _extraer_oracion(words_data: Dict, mult: int, offset_us: int = 0) -> List[Dict]:
        text_list = words_data.get("text", []) or []
        start_raw = words_data.get("start_time", []) or []
        end_raw = words_data.get("end_time", []) or []
        if not text_list or not start_raw:
            return []

        oracion = []
        for i, palabra_raw in enumerate(text_list):
            palabra = (palabra_raw or "").strip()
            if not palabra:
                continue
            start = int(start_raw[i]) * mult if i < len(start_raw) else 0
            end = int(end_raw[i]) * mult if i < len(end_raw) else 0
            if end <= start:
                end = start + 100_000  # 100ms estimado
            # CRITICO: start_time/end_time son relativos al inicio de la
            # oracion; hay que sumar el offset absoluto del segmento en el
            # timeline para no anclar todas las oraciones a 0.00s.
            oracion.append({
                "word": palabra,
                "start_us": start + offset_us,
                "end_us": end + offset_us,
            })
        return oracion


def main():
    if len(sys.argv) < 2:
        print("Uso: python utils/extract_autocaption.py <ruta_draft_content.json>")
        sys.exit(1)

    json_path = sys.argv[1]
    if not Path(json_path).exists():
        print(f"ERROR: no se encontro el archivo {json_path}")
        sys.exit(1)

    oraciones, stats = AutocaptionExtractor.extract(json_path)
    if "error" in stats:
        print(f"ERROR: {stats['error']}")
        sys.exit(1)

    print("Estadisticas:")
    print(f"  Metodo:               {stats.get('metodo')}")
    print(f"  Materiales de texto:  {stats['total_materials']}")
    print(f"  Oraciones extraidas:  {stats['oraciones_extraidas']}")
    total_palabras = sum(len(o) for o in oraciones)
    print(f"  Total de palabras:    {total_palabras}")

    out = Path(json_path).parent / "oraciones_autocaption.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(oraciones, f, ensure_ascii=False, indent=2)
    print(f"\nGuardado en: {out}")

    for i, oracion in enumerate(oraciones[:5]):
        palabras = " ".join(p["word"] for p in oracion)
        t0 = oracion[0]["start_us"] / 1e6
        t1 = oracion[-1]["end_us"] / 1e6
        print(f"  {i+1}. [{t0:.2f}s-{t1:.2f}s] {palabras}")


if __name__ == "__main__":
    main()

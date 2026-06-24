"""
Diagnostico de solo lectura de un draft_content.json de CapCut.

Genera un reporte en texto explicando que hay dentro del draft: cuantos
materiales de texto, en que formato estan los 'words', que tracks existen,
y -- lo mas util -- una conclusion en espanol de por que el sistema podria
estar extrayendo 0 oraciones.

Es la version reutilizable (para cualquier draft, y usable desde la UI) de
lo que antes era el script hardcodeado diagnostico_maria.py.

NUNCA modifica el draft: solo lee.
"""

from __future__ import annotations

import json
from pathlib import Path


def diagnosticar_draft(json_path) -> str:
    """Lee un draft_content.json y devuelve un reporte de texto con el
    estado de su auto-caption. No modifica nada.

    Args:
        json_path: ruta al draft_content.json.

    Returns:
        Un string multilinea listo para mostrar (en consola o en la UI).
    """
    json_path = Path(json_path)
    lineas = []

    def out(s=""):
        lineas.append(s)

    if not json_path.is_file():
        return f"❌ No se encontro el draft en:\n  {json_path}"

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except json.JSONDecodeError as e:
        return f"❌ El draft no es un JSON valido: {e}"
    except OSError as e:
        return f"❌ No se pudo leer el draft: {e}"

    duracion_us = draft.get("duration", 0) or 0
    out(f"Duracion del video: {duracion_us / 1_000_000:.1f}s")

    materials_texts = draft.get("materials", {}).get("texts", []) or []
    out(f"Materiales de texto en el draft: {len(materials_texts)}")

    con_words_content = 0   # formato viejo: words dentro de content
    con_words_raiz = 0      # formato nuevo: words a nivel raiz
    con_words_raiz_vacio = 0
    con_recognize = 0       # auto-caption real (recognize_task_id poblado)

    for mat in materials_texts:
        # Formato viejo: content es JSON string con "words" adentro
        content_raw = mat.get("content")
        if isinstance(content_raw, str):
            try:
                parsed = json.loads(content_raw)
                if parsed.get("words"):
                    con_words_content += 1
            except (json.JSONDecodeError, AttributeError):
                pass

        # Formato nuevo: words a nivel raiz del material (arrays paralelos)
        words_raiz = mat.get("words")
        if isinstance(words_raiz, dict):
            textos = words_raiz.get("text") or []
            # contar solo palabras reales (descartando separadores " ")
            reales = [t for t in textos if (t or "").strip()]
            if reales:
                con_words_raiz += 1
            else:
                con_words_raiz_vacio += 1

        if (mat.get("recognize_task_id") or "").strip():
            con_recognize += 1

    out("")
    out("Formato de los datos de palabras:")
    out(f"  - con 'words' dentro de content (formato viejo): {con_words_content}")
    out(f"  - con 'words' a nivel raiz CON datos (formato nuevo): {con_words_raiz}")
    out(f"  - con 'words' a nivel raiz VACIO: {con_words_raiz_vacio}")
    out(f"  - con recognize_task_id (auto-caption real): {con_recognize}")

    # Tracks
    out("")
    out("Tracks del draft:")
    tracks = draft.get("tracks", []) or []
    tracks_texto_auto = 0
    for i, t in enumerate(tracks):
        tipo = t.get("type", "?")
        nombre = t.get("name", "") or "(sin nombre)"
        n = len(t.get("segments", []) or [])
        out(f"  [{i}] tipo={tipo} nombre={nombre!r} segmentos={n}")
        if tipo == "text" and str(t.get("name", "")).startswith("AUTO_"):
            tracks_texto_auto += 1

    # Conclusion accionable
    out("")
    out("=" * 50)
    hay_datos = con_words_content > 0 or con_words_raiz > 0
    if hay_datos:
        out("✅ SI hay datos de auto-caption en el draft.")
        if tracks_texto_auto > 0:
            out(f"   Tambien hay {tracks_texto_auto} track(s) AUTO_ ya generados")
            out("   (resultado de una corrida anterior; se limpian solos).")
        out("   Si el generador igual dio 0, puede ser un tema de parseo:")
        out("   guarda este reporte para revisar.")
    else:
        out("❌ NO hay datos de auto-caption procesables en el draft.")
        if con_words_raiz_vacio > 0:
            out(f"   Hay {con_words_raiz_vacio} materiales de texto pero con")
            out("   'words' VACIO -- el auto-caption se genero sin reconocer voz,")
            out("   o se perdio en una corrida anterior.")
        out("")
        out("   QUE HACER:")
        out("   1. Abri el proyecto en CapCut.")
        out("   2. Genera los Subtitulos automaticos sobre el clip de video.")
        out("   3. Guarda (Ctrl+S) y CERRA CapCut por completo.")
        out("   4. Volve a analizar.")
    out("=" * 50)

    return "\n".join(lineas)


def _main_cli():
    """Permite correrlo desde linea de comandos:
        python -m utils.diagnostico <ruta_al_draft_content.json>
    """
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m utils.diagnostico <ruta_al_draft_content.json>")
        sys.exit(1)
    print(diagnosticar_draft(sys.argv[1]))


if __name__ == "__main__":
    _main_cli()

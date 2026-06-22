"""
DIAGNOSTICO de solo lectura para "mariaaa baic".

NO modifica nada (no llama a script.save(), no borra tracks). Solo lee
draft_content.json y muestra qué encuentra, para entender por qué
generar_subtitulos_maria.py extrajo 0 oraciones.

Uso:
    python diagnostico_maria.py
"""

import json
from pathlib import Path

CARPETA_DRAFTS = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
NOMBRE_DRAFT = "mariaaa baic"


def main():
    json_path = Path(CARPETA_DRAFTS) / NOMBRE_DRAFT / "draft_content.json"
    if not json_path.is_file():
        print(f"ERROR: no se encontro el draft en:\n  {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        draft = json.load(f)

    duracion_us = draft.get("duration", 0)
    print(f"Duracion del video: {duracion_us/1_000_000:.1f}s")

    materials_texts = draft.get("materials", {}).get("texts", []) or []
    print(f"\nTotal de materiales de texto en el draft: {len(materials_texts)}")

    con_words = 0
    con_content_json = 0
    ejemplos = []

    for mat in materials_texts:
        mid = mat.get("id", "")[:8]
        content_raw = mat.get("content")

        # Caso A: content es un JSON string con "words" adentro (formato
        # que lee DraftManager/camino 1)
        parsed = None
        if isinstance(content_raw, str):
            try:
                parsed = json.loads(content_raw)
            except Exception:
                parsed = None

        if parsed and isinstance(parsed, dict) and parsed.get("words"):
            con_content_json += 1
            if len(ejemplos) < 5:
                texto = "".join(w.get("text", "") for w in parsed["words"][:6])
                ejemplos.append(f"  [content/words] id={mid}... texto~'{texto}...'")

        # Caso B: el material tiene "words" como array paralelo directo
        # (formato que lee el camino 2, respaldo)
        if mat.get("words"):
            con_words += 1
            if len(ejemplos) < 10:
                w = mat["words"]
                if isinstance(w, list) and w and isinstance(w[0], dict):
                    texto = "".join(x.get("text", "") for x in w[:6])
                else:
                    texto = str(w)[:60]
                ejemplos.append(f"  [material.words] id={mid}... texto~'{texto}...'")

    print(f"Materiales con 'words' dentro de content (JSON string): {con_content_json}")
    print(f"Materiales con 'words' como array directo en el material: {con_words}")

    # Volcado CRUDO del primer material completo (todas sus claves), para
    # ver si el texto/tiempos reales viven en otro campo que no estamos
    # mirando todavia (p.ej. "content" como dict en vez de words, o un
    # campo "text" separado a nivel raiz del material).
    if materials_texts:
        print("\nMaterial #0 COMPLETO (todas sus claves, valores recortados):")
        primero = materials_texts[0]
        for k, v in primero.items():
            v_str = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
            if len(v_str) > 200:
                v_str = v_str[:200] + "...(recortado)"
            print(f"  {k}: {v_str}")

    print("\nEjemplos encontrados (hasta 10):")
    if ejemplos:
        for e in ejemplos:
            print(e)
    else:
        print("  (ninguno)")

    # Tracks: mostrar TODOS los tipos tal como vienen en el archivo, sin
    # asumir que el valor es literalmente "text" (si el draft usa otra
    # capitalizacion, un numero, etc, un filtro exacto los esconde y
    # parece que "no hay tracks" cuando si los hay).
    print("\nTODOS los tracks del draft (sin filtrar por tipo):")
    tracks = draft.get("tracks", []) or []
    if not tracks:
        print("  (el array 'tracks' esta vacio o no existe)")
    for i, track in enumerate(tracks):
        tipo = track.get("type")
        nombre = track.get("name", "(sin nombre)")
        segs = track.get("segments", []) or []
        print(f"  [{i}] type={tipo!r} name={nombre!r} segmentos={len(segs)}")

    # Cuantos segmentos (de CUALQUIER track) referencian alguno de los 217
    # material_id de texto que ya encontramos arriba
    ids_texto = {m.get("id") for m in materials_texts}
    refs_a_texto = 0
    for track in tracks:
        for seg in track.get("segments", []) or []:
            if seg.get("material_id") in ids_texto:
                refs_a_texto += 1
    print(f"\nSegmentos (en cualquier track) que referencian esos 217 material_id de texto: {refs_a_texto}")

    print("\n" + "=" * 60)
    if con_content_json == 0 and con_words == 0:
        print("DIAGNOSTICO: no se encontro NINGUN material con 'words'.")
        print("Esto pasa cuando el auto-caption original ya no esta en el")
        print("draft (se perdio o se reemplazo en una corrida anterior),")
        print("igual que el Error #2 documentado en el handoff original.")
    else:
        print("DIAGNOSTICO: SI hay datos de auto-caption en el archivo.")
        print("Si el generador igual dio 0, el problema esta en el PARSEO")
        print("(formato de 'words' distinto al esperado), no en que falten")
        print("los datos. Compartir este output para ajustar el parser.")
    print("=" * 60)


if __name__ == "__main__":
    main()

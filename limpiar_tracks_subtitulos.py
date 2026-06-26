# =====================================================================
# limpiar_tracks_subtitulos.py
# =====================================================================
# Borra los tracks de TEXTO generados por SubtitleEngine en una corrida
# anterior (prefijo "AUTO_sub_", definido en SubtitleEngine.TRACK_PREFIX),
# SIN tocar:
#   - el auto-caption nativo de CapCut (el track de texto SIN ese
#     prefijo, que es la fuente de datos real para volver a generar)
#   - cualquier otro track de video/audio/texto manual del usuario
#
# POR QUE HACE FALTA: el sistema viejo (entrv fede baic) usaba el
# prefijo "AUTO_pos_N" y ya tenia su propio limpiar_tracks_auto.py. El
# sistema nuevo (core/capcut_engine.py + core/subtitle_engine.py) usa el
# prefijo DISTINTO "AUTO_sub_N" (ver SubtitleEngine.TRACK_PREFIX) - el
# script de limpieza viejo no lo reconoce, asi que cada vez que se
# corre generar_subtitulos_baic_v5.py sobre un draft que ya tenia una
# corrida anterior (por ejemplo, una corrida con el bug del eje Y ya
# corregido en el codigo pero generada ANTES del fix), los tracks viejos
# quedan mezclados con los nuevos sin que nada los borre.
#
# USO:
#   python limpiar_tracks_subtitulos.py "nombre del draft"
#   (el nombre tal cual aparece en la carpeta de CapCut, sin la ruta)
# =====================================================================

import json
import os
import sys
import shutil
from datetime import datetime

# Ajustar si tu carpeta de drafts de CapCut es otra
CARPETA_DRAFTS = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"

PREFIJO_A_BORRAR = "AUTO_sub_"


def main():
    if len(sys.argv) < 2:
        print('Uso: python limpiar_tracks_subtitulos.py "nombre del draft"')
        print()
        print("Drafts disponibles en tu carpeta de CapCut:")
        try:
            for nombre in sorted(os.listdir(CARPETA_DRAFTS)):
                ruta = os.path.join(CARPETA_DRAFTS, nombre)
                if os.path.isdir(ruta):
                    print(f"  - {nombre}")
        except Exception as e:
            print(f"  (no se pudo listar: {e})")
        sys.exit(1)

    nombre_draft = sys.argv[1]
    ruta_draft = os.path.join(CARPETA_DRAFTS, nombre_draft, "draft_content.json")

    if not os.path.exists(ruta_draft):
        raise SystemExit(f"No se encontro el draft en: {ruta_draft}")

    with open(ruta_draft, "r", encoding="utf-8") as f:
        data = json.load(f)

    tracks = data.get("tracks", [])
    tracks_a_borrar = [
        t for t in tracks
        if t.get("type") == "text" and (t.get("name") or "").startswith(PREFIJO_A_BORRAR)
    ]

    if not tracks_a_borrar:
        print(f"No se encontro ningun track con prefijo '{PREFIJO_A_BORRAR}'. Nada para borrar.")
        return

    print(f"Se van a borrar {len(tracks_a_borrar)} tracks:")
    total_segs = 0
    for t in tracks_a_borrar:
        n_segs = len(t.get("segments", []))
        total_segs += n_segs
        print(f"  - {t.get('name')!r} ({n_segs} segmentos)")
    print(f"Total de segmentos de texto a eliminar: {total_segs}")

    # Tambien hay que eliminar los MATERIALES de texto que esos
    # segmentos referenciaban, para no dejar basura huerfana en
    # materials.texts (no rompe nada si queda, pero ensucia el archivo).
    material_ids_a_borrar = set()
    for t in tracks_a_borrar:
        for seg in t.get("segments", []):
            mid = seg.get("material_id")
            if mid:
                material_ids_a_borrar.add(mid)

    # Backup antes de tocar nada
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_backup = os.path.join(
        CARPETA_DRAFTS, nombre_draft, f"draft_content_BACKUP_{timestamp}.json"
    )
    shutil.copy2(ruta_draft, ruta_backup)
    print(f"\nBackup guardado en: {ruta_backup}")

    # Borrar los tracks
    data["tracks"] = [t for t in tracks if t not in tracks_a_borrar]

    # Borrar los materiales huerfanos
    texts_originales = data["materials"].get("texts", [])
    data["materials"]["texts"] = [
        m for m in texts_originales if m.get("id") not in material_ids_a_borrar
    ]
    n_materiales_borrados = len(texts_originales) - len(data["materials"]["texts"])

    with open(ruta_draft, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"\nListo. Se borraron {len(tracks_a_borrar)} tracks, {total_segs} segmentos "
          f"y {n_materiales_borrados} materiales de texto huerfanos.")
    print(f"El draft '{nombre_draft}' quedo limpio para volver a generar subtitulos.")


if __name__ == "__main__":
    main()

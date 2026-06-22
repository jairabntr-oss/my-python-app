"""
Limpia los tracks AUTO_ (texto y audio) residuales de una corrida anterior
en "mariaaa baic", para poder volver a generar subtitulos desde cero sin
que choquen contra los tracks ya existentes.

NO toca: el video, ni tracks manuales/sin prefijo AUTO_.

Antes de correr esto: CERRA CapCut por completo.

Uso:
    python limpiar_maria.py
(parado en la carpeta del repo, con pycapcut instalado)
"""

import sys
from pathlib import Path

import pycapcut as cc
from core.cleaner import Cleaner

# ─── CONFIGURACION ────────────────────────────────────────────────────────
CARPETA_DRAFTS = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
NOMBRE_DRAFT = "mariaaa baic"


def main():
    print("=" * 60)
    print(f"  LIMPIEZA DE TRACKS AUTO_ - {NOMBRE_DRAFT}")
    print("=" * 60)

    json_path = Path(CARPETA_DRAFTS) / NOMBRE_DRAFT / "draft_content.json"
    if not json_path.is_file():
        print(f"\nERROR: no se encontro el draft en:\n  {json_path}")
        sys.exit(1)

    print("\nCERRA CapCut si esta abierto. Presiona Enter para continuar...")
    input()

    script = cc.DraftFolder(CARPETA_DRAFTS).load_template(NOMBRE_DRAFT)

    print("\nTracks de texto ANTES de limpiar:")
    for t in script.imported_tracks:
        if "text" in str(t.track_type).lower():
            print(f"  {t.name!r}: {len(t.segments)} segmentos")

    cleaner = Cleaner(script)
    n_texto = cleaner.limpiar_tracks_texto()
    n_audio = cleaner.limpiar_tracks_audio()
    script.save()

    print(f"\nTracks de texto AUTO_ eliminados: {n_texto}")
    print(f"Tracks de audio AUTO_ eliminados: {n_audio}")

    # confirmar releyendo el draft ya guardado
    script2 = cc.DraftFolder(CARPETA_DRAFTS).load_template(NOMBRE_DRAFT)
    print("\nTracks de texto DESPUES de limpiar (verificado):")
    for t in script2.imported_tracks:
        if "text" in str(t.track_type).lower():
            print(f"  {t.name!r}: {len(t.segments)} segmentos")

    print("\n" + "=" * 60)
    print("LISTO. Ahora podes correr generar_subtitulos_maria.py de nuevo.")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"\nError fatal: {e}")
        traceback.print_exc()
        sys.exit(1)

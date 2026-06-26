"""
Script para agregar clicks de audio a "entrv señores - clip2_fantastica".

DIFERENCIA respecto a agregar_clicks_arrizzo8.py: ese script extrae
oraciones del auto-caption ORIGINAL via AutocaptionExtractor. En este
draft el usuario ya corto partes de video/audio Y edito los subtitulos
a mano (el auto-caption original ya no existe, y los tiempos del
draft viejo de 65.6s no corresponden al draft nuevo de ~43.6s).

Por eso, en vez de AutocaptionExtractor, este script construye
"oraciones" directamente desde los SEGMENTOS DE TEXTO YA EXISTENTES en
el draft actual (los AUTO_sub_* ya editados a mano), agrupando por
BLOQUE VISUAL real: un bloque nuevo arranca cuando una palabra empieza
en o despues del momento en que el bloque anterior deja de mostrarse
en pantalla (criterio confirmado con el usuario, en vez de intentar
adivinar "oraciones" gramaticales por pausas, que dio cortes raros con
solo 30% de margen de error en los bordes).

ClickEngine.generate() en si NO se modifico - sigue siendo el mismo
motor ya corregido (Error #12: add_material explicito; Error #13: 2
clicks por bloque, no 3). Solo cambia de donde vienen las "oraciones"
que se le pasan.

Uso:
    python agregar_clicks_clip2_fantastica.py [draft_folder] [ruta_sonido]
"""

import sys
import json
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from core.click_engine import ClickEngine
import pycapcut as cc


DRAFT_NAME = "entrv señores - clip2_fantastica"
DEFAULT_SONIDO = _ROOT / "assets" / "click_sonido.mp3"


def construir_bloques_visuales(json_path: str):
    """Agrupa los segmentos de texto YA EXISTENTES en el draft (editados
    a mano) en bloques visuales reales, en el mismo formato que espera
    ClickEngine.generate() (lista de "oraciones", cada una lista de
    palabras con start_us/end_us).

    Un bloque nuevo arranca cuando el start_us de una palabra es >= al
    fin maximo visible acumulado del bloque actual (o sea, el bloque
    anterior ya termino de mostrarse en pantalla).
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    texts_by_id = {t["id"]: t for t in data["materials"]["texts"]}
    palabras = []
    for track in data.get("tracks", []):
        if track.get("type") != "text":
            continue
        for seg in track.get("segments", []):
            mat = texts_by_id.get(seg.get("material_id"))
            if mat is None:
                continue
            try:
                content = json.loads(mat["content"])
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

    bloques = []
    bloque_actual = []
    fin_max_bloque = None
    for p in palabras:
        if fin_max_bloque is not None and p["start_us"] >= fin_max_bloque:
            bloques.append(bloque_actual)
            bloque_actual = []
            fin_max_bloque = None
        bloque_actual.append(p)
        fin_max_bloque = p["end_us"] if fin_max_bloque is None else max(fin_max_bloque, p["end_us"])
    if bloque_actual:
        bloques.append(bloque_actual)

    return bloques


def main():
    print("=" * 60)
    print(f"  AGREGAR CLICKS - {DRAFT_NAME.upper()}")
    print("=" * 60)

    if len(sys.argv) >= 2:
        draft_folder = sys.argv[1]
    else:
        draft_folder = str(
            Path.home()
            / "AppData"
            / "Local"
            / "CapCut"
            / "User Data"
            / "Projects"
            / "com.lveditor.draft"
        )
        print(f"\n⚠️  No se indicó carpeta. Usando: {draft_folder}")

    ruta_sonido = sys.argv[2] if len(sys.argv) >= 3 else str(DEFAULT_SONIDO)

    json_path = Path(draft_folder) / DRAFT_NAME / "draft_content.json"

    if not json_path.exists():
        print(f"\n❌ Proyecto no encontrado: {json_path}")
        sys.exit(1)

    if not Path(ruta_sonido).exists():
        print(f"\n❌ Archivo de click no encontrado: {ruta_sonido}")
        print("   Colocá el archivo en assets/click_sonido.mp3 o pasá la ruta como argumento.")
        sys.exit(1)

    print(f"\n✅ Proyecto: {json_path}")
    print(f"✅ Sonido: {ruta_sonido}")
    print("\n⚠️  CERRÁ CAPCUT. Presioná Enter para continuar...")
    input()

    # ── Paso 1: construir bloques visuales desde el draft YA EDITADO ─────────
    print("\n📝 Paso 1: Reconstruyendo bloques visuales desde los subtítulos editados...")
    bloques = construir_bloques_visuales(str(json_path))

    if not bloques:
        print("❌ No se encontraron bloques de texto en el draft.")
        sys.exit(1)

    total_palabras = sum(len(b) for b in bloques)
    print(f"   Bloques visuales: {len(bloques)}")
    print(f"   Palabras: {total_palabras}")
    print(f"   Clicks estimados (2 por bloque): {len(bloques) * 2}")

    # ── Paso 2: Cargar draft (sin limpiar tracks de audio - no hay residuales) ─
    print("\n📂 Paso 2: Cargando draft...")
    draft_folder_obj = cc.DraftFolder(draft_folder)
    script = draft_folder_obj.load_template(DRAFT_NAME)

    # ── Paso 3: Generar clicks ────────────────────────────────────────────────
    print("\n🔊 Paso 3: Generando clicks de audio...")
    click_engine = ClickEngine(script, ruta_sonido)
    resultado = click_engine.generate(bloques, modo="2_por_oracion")

    print(f"   Clicks insertados: {resultado['total_clicks']}")
    print(f"   Track: {resultado['track_name']}")
    print(f"   Modo: {resultado['modo']}")

    print("\n✅ ¡Clicks agregados correctamente!")
    print(f"\n💡 Abrí CapCut y verificá el proyecto '{DRAFT_NAME}'.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación interrumpida.")
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"\n❌ Error fatal: {e}")
        traceback.print_exc()
        sys.exit(1)

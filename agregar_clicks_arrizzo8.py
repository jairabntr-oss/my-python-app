"""
Script específico para agregar clicks de audio al proyecto "arrizzo 8".

Uso:
    python agregar_clicks_arrizzo8.py <draft_folder> [ruta_sonido]

Ejemplo (Windows):
    python agregar_clicks_arrizzo8.py "C:\\Users\\user2\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft"

Si no se provee ruta_sonido, usa assets/click_sonido.mp3 por defecto.

⚠️  IMPORTANTE:
  - Ejecutá generar_arrizzo8.py PRIMERO para tener los subtítulos.
  - Cerrá CapCut antes de ejecutar este script.
"""

import sys
import json
from pathlib import Path

_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from utils.extract_autocaption import AutocaptionExtractor
from core.cleaner import Cleaner
from core.click_engine import ClickEngine
import pycapcut as cc


DRAFT_NAME = "arrizzo 8"
DEFAULT_SONIDO = _ROOT / "assets" / "click_sonido.mp3"


def main():
    print("=" * 60)
    print(f"  AGREGAR CLICKS - {DRAFT_NAME.upper()}")
    print("=" * 60)

    # ── Argumentos ────────────────────────────────────────────────────────────
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

    # ── Verificar archivos ────────────────────────────────────────────────────
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

    # ── Paso 1: Extraer oraciones ─────────────────────────────────────────────
    print("\n📝 Paso 1: Extrayendo oraciones del auto-caption...")
    oraciones, stats = AutocaptionExtractor.extract(str(json_path))

    if "error" in stats or not oraciones:
        print("❌ No se encontraron oraciones. Ejecutá generar_arrizzo8.py primero.")
        sys.exit(1)

    print(f"   Oraciones: {len(oraciones)}")
    print(f"   Palabras: {sum(len(o) for o in oraciones)}")

    # ── Paso 2: Cargar draft y limpiar ────────────────────────────────────────
    print("\n🧹 Paso 2: Cargando draft y limpiando tracks de audio residuales...")

    draft_folder_obj = cc.DraftFolder(draft_folder)
    script = draft_folder_obj.load_template(DRAFT_NAME)

    cleaner = Cleaner(script)
    n_audio = cleaner.limpiar_tracks_audio()
    print(f"   Tracks de audio 'AUTO_' eliminados: {n_audio}")

    # ── Paso 3: Generar clicks ────────────────────────────────────────────────
    print("\n🔊 Paso 3: Generando clicks de audio...")

    click_engine = ClickEngine(script, ruta_sonido)
    resultado = click_engine.generate(oraciones, modo="2_por_oracion")

    print(f"   Clicks insertados: {resultado['total_clicks']}")
    print(f"   Track: {resultado['track_name']}")
    print(f"   Modo: {resultado['modo']}")

    print("\n✅ ¡Clicks agregados correctamente!")
    print("\n💡 Abrí CapCut y verificá el proyecto 'arrizzo 8'.")


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

"""
Script específico para generar subtítulos karaoke del proyecto "arrizzo 8".

Uso:
    python generar_arrizzo8.py <draft_folder>

Ejemplo (Windows):
    python generar_arrizzo8.py "C:\\Users\\user2\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft"

El script:
1. Lee el draft_content.json del proyecto "arrizzo 8"
2. Extrae las oraciones del auto-caption
3. Limpia tracks AUTO_ existentes
4. Genera los subtítulos karaoke acumulativo
5. Guarda el draft

⚠️  IMPORTANTE: Cerrá CapCut antes de ejecutar este script.
"""

import sys
import json
from pathlib import Path

# Agregar el directorio raíz al path para importaciones
_ROOT = Path(__file__).parent
sys.path.insert(0, str(_ROOT))

from utils.extract_autocaption import AutocaptionExtractor
from core.cleaner import Cleaner
from core.subtitle_engine import SubtitleEngine
import pycapcut as cc


DRAFT_NAME = "arrizzo 8"
CONFIG_PATH = _ROOT / "config" / "settings.json"


def cargar_perfil() -> dict:
    """Carga el perfil de estilo desde settings.json."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)
        return settings.get("subtitle_style", {})
    except Exception as e:
        print(f"⚠️  No se pudo cargar settings.json ({e}). Usando valores por defecto.")
        return {
            "text_size": 30,
            "text_color": "#FFFFFF",
            "scale_x": 3.037,
            "scale_y": 3.037,
            "shadow_enabled": True,
            "shadow_alpha": 0.33,
        }


def main():
    print("=" * 60)
    print(f"  GENERAR SUBTÍTULOS - {DRAFT_NAME.upper()}")
    print("=" * 60)

    # ── Obtener carpeta de drafts ─────────────────────────────────────────────
    if len(sys.argv) >= 2:
        draft_folder = sys.argv[1]
    else:
        # Intentar ruta por defecto de Windows
        draft_folder = (
            r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
        )
        print(f"\n⚠️  No se indicó carpeta. Usando: {draft_folder}")

    # ── Verificar que el proyecto existe ─────────────────────────────────────
    proyecto_path = Path(draft_folder) / DRAFT_NAME
    json_path = proyecto_path / "draft_content.json"

    if not json_path.exists():
        print(f"\n❌ No se encontró el archivo: {json_path}")
        print("   Verificá que CapCut tenga el proyecto 'arrizzo 8' y que la ruta sea correcta.")
        sys.exit(1)

    print(f"\n✅ Proyecto encontrado: {json_path}")
    print("\n⚠️  CERRÁ CAPCUT si está abierto. Presioná Enter para continuar...")
    input()

    # ── Paso 1: Extraer oraciones del auto-caption ────────────────────────────
    print("\n📝 Paso 1: Extrayendo oraciones del auto-caption...")
    oraciones, stats = AutocaptionExtractor.extract(str(json_path))

    if "error" in stats:
        print(f"❌ {stats['error']}")
        sys.exit(1)

    print(f"   Materiales totales: {stats['total_materials']}")
    print(f"   Con 'words': {stats['materiales_con_words']}")
    print(f"   Oraciones extraídas: {stats['oraciones_extraidas']}")

    if not oraciones:
        print("\n❌ No se encontraron oraciones procesables.")
        print("   El proyecto puede no tener auto-caption sin editar.")
        sys.exit(1)

    total_palabras = sum(len(o) for o in oraciones)
    print(f"   Total de palabras: {total_palabras}")

    # Preview de las primeras 3 oraciones
    print("\n   Preview:")
    for i, oracion in enumerate(oraciones[:3]):
        palabras = " ".join(p["word"] for p in oracion)
        t_inicio = oracion[0]["start_us"] / 1e6
        t_fin = oracion[-1]["end_us"] / 1e6
        print(f"     {i+1}. [{t_inicio:.2f}s-{t_fin:.2f}s] {palabras}")

    # ── Paso 2: Cargar draft y limpiar tracks viejos ──────────────────────────
    print("\n🧹 Paso 2: Cargando draft y limpiando tracks residuales...")
    profile = cargar_perfil()

    draft_folder_obj = cc.DraftFolder(draft_folder)
    script = draft_folder_obj.load_template(DRAFT_NAME)

    cleaner = Cleaner(script)
    n_texto = cleaner.limpiar_tracks_texto()
    print(f"   Tracks de texto 'AUTO_' eliminados: {n_texto}")

    # ── Paso 3: Generar subtítulos ────────────────────────────────────────────
    print("\n✨ Paso 3: Generando subtítulos karaoke...")

    engine = SubtitleEngine(script, profile)
    resultado = engine.generate(oraciones)

    print(f"   Palabras generadas: {resultado['total_palabras']}")
    print(f"   Bloques creados: {resultado['total_bloques']}")
    print(f"   Pares de overlap detectados: {resultado['pares_overlap']}")

    print("\n✅ ¡Subtítulos generados correctamente!")
    print(f"   Track creado: {resultado['track_name']}")
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

"""
Genera subtitulos karaoke (multi-track) para "mariaaa baic" usando el
pipeline ya arreglado del repo (extractor + Cleaner + SubtitleEngine).

Por que se usa "mariaaa baic" (la copia con auto-caption nativo intacto)
y NO "video maria BAIC": en ese segundo draft el auto-caption original ya
se habia perdido en corridas anteriores (quedaban solo palabras sueltas
de ~33ms, sin datos de origen recuperables). "mariaaa baic" es el backup
que todavia tiene el auto-caption nativo real (43 oraciones, 217 palabras
con sus timings), que es la fuente de datos.

Que hace, en orden:
  1. Extrae las 43 oraciones de auto-caption (texto + tiempos reales).
  2. Carga el draft UNA sola vez.
  3. Borra el auto-caption nativo viejo (ya con los datos a salvo) y
     cualquier track AUTO_ residual de corridas anteriores.
  4. Genera los subtitulos karaoke acumulativo, repartidos en varios
     tracks AUTO_sub_N para evitar el error de superposicion de pycapcut.
  5. Guarda el draft.

Antes de correr esto: CERRA CapCut por completo.

Uso:
    python generar_subtitulos_maria.py
(parado en la carpeta del repo, con pycapcut instalado: pip install pycapcut)
"""

import sys
import json
from pathlib import Path

import pycapcut as cc
from utils.extract_autocaption import AutocaptionExtractor
from core.cleaner import Cleaner
from core.subtitle_engine import SubtitleEngine
from config import cargar_perfil_estilo

# ─── CONFIGURACION ────────────────────────────────────────────────────────
CARPETA_DRAFTS = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
NOMBRE_DRAFT = "mariaaa baic"

# El estilo (tamaño, color, escala, sombra, fuente) se carga de
# config/user_profile.json - tu calibracion real documentada en
# PLAN_TECNICO_COMPLETO.md - en vez de estar hardcodeado aca.
PERFIL_ESTILO = cargar_perfil_estilo()


def main():
    print("=" * 60)
    print(f"  GENERAR SUBTITULOS KARAOKE - {NOMBRE_DRAFT}")
    print("=" * 60)

    json_path = Path(CARPETA_DRAFTS) / NOMBRE_DRAFT / "draft_content.json"
    if not json_path.is_file():
        print(f"\nERROR: no se encontro el draft en:\n  {json_path}")
        print("Verifica el nombre exacto del proyecto en CapCut.")
        sys.exit(1)

    print("\nPaso 1: extrayendo oraciones de auto-caption...")
    oraciones, stats = AutocaptionExtractor.extract(str(json_path))
    print(f"  Metodo usado: {stats.get('metodo')}")
    print(f"  Oraciones extraidas: {stats['oraciones_extraidas']}")
    total_palabras = sum(len(o) for o in oraciones)
    print(f"  Palabras totales: {total_palabras}")

    if not oraciones:
        print("\nNo se encontraron oraciones procesables. Nada que hacer.")
        sys.exit(0)

    print("\n  Preview (primeras 5 oraciones):")
    for i, o in enumerate(oraciones[:5]):
        texto = " ".join(p["word"] for p in o)
        t0, t1 = o[0]["start_us"] / 1e6, o[-1]["end_us"] / 1e6
        print(f"    [{i+1}] [{t0:.2f}s-{t1:.2f}s] {texto}")

    print("\nCERRA CapCut si esta abierto. Presiona Enter para continuar...")
    input()

    print("\nPaso 2: cargando el draft...")
    script = cc.DraftFolder(CARPETA_DRAFTS).load_template(NOMBRE_DRAFT)

    print("Paso 3: limpiando auto-caption nativo viejo y tracks AUTO_ residuales...")
    cleaner = Cleaner(script)
    n_nativo = cleaner.limpiar_autocaption_nativo()
    n_auto = cleaner.limpiar_tracks_texto()
    print(f"  Segmentos de auto-caption nativo eliminados: {n_nativo}")
    print(f"  Tracks AUTO_ residuales eliminados: {n_auto}")

    print("\nPaso 4: generando subtitulos karaoke (esto guarda el draft)...")
    resultado = SubtitleEngine(script, PERFIL_ESTILO).generate(oraciones)

    print("\n" + "=" * 60)
    if resultado.get("success"):
        print("LISTO. Generacion completada:")
        print(f"  Palabras generadas: {resultado['total_palabras']}")
        print(f"  Bloques:            {resultado['total_bloques']}")
        print(f"  Dialogos simultaneos detectados: {resultado['pares_overlap']}")
        print(f"  Tracks usados:      {resultado['total_tracks']} (AUTO_sub_0 .. AUTO_sub_{resultado['total_tracks']-1})")
        print(f"  Materiales con sombra/fuente aplicada: {resultado.get('materiales_con_sombra', 0)}")
        print("\nAbri (o reabri) el proyecto en CapCut para revisar el resultado.")
    else:
        print(f"ERROR: {resultado}")
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

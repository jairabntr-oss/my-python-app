"""
Script de integración completa para validar el sistema con un video real.

Uso:
    python test_integration_real.py "C:\ruta\al\draft_arrizzo8.json" "tiggo 4"
"""

import sys
import json
from pathlib import Path
from utils.capcut_parser import CapcutParser
from services.draft_service import DraftService
from config import settings


def main():
    # Configuración
    if len(sys.argv) < 3:
        print("❌ Uso: python test_integration_real.py <json_path> <draft_name>")
        print("   Ejemplo: python test_integration_real.py C:\\Users\\user2\\Desktop\\draft_arrizzo8.json 'arrizzo 8'")
        sys.exit(1)
    
    json_path = sys.argv[1]
    draft_name = sys.argv[2]
    
    print(f"\n" + "="*80)
    print(f"🚀 PRUEBA DE INTEGRACIÓN - Sistema CapCut Auto-Subtitle")
    print(f"="*80)
    
    # PASO 1: Diagnosticar JSON
    print(f"\n✅ PASO 1: Diagnosticar JSON")
    print("-" * 80)
    
    if not Path(json_path).exists():
        print(f"❌ Archivo no encontrado: {json_path}")
        sys.exit(1)
    
    CapcutParser.diagnosticar_y_mostrar(json_path)
    
    # PASO 2: Extraer captions
    print(f"\n✅ PASO 2: Extraer captions")
    print("-" * 80)
    
    oraciones, error = CapcutParser.extraer_captions(json_path)
    
    if error:
        print(f"❌ {error}")
        sys.exit(1)
    
    print(f"✅ Oraciones extraídas: {len(oraciones)}")
    print(f"✅ Total de palabras: {sum(len(o) for o in oraciones)}")
    
    # PASO 3: Validar datos con DraftService
    print(f"\n✅ PASO 3: Validar datos")
    print("-" * 80)
    
    # Cargar perfil/configuración
    try:
        with open("config/settings.json", 'r') as f:
            settings_data = json.load(f)
        profile = settings_data.get("subtitle_style", {})
    except:
        print("⚠️  No se pudo cargar settings.json, usando valores por defecto")
        profile = {
            "text_size": 30,
            "text_color": "#FFFFFF",
            "scale_x": 1.67,
            "scale_y": 1.67,
            "shadow_enabled": True,
            "shadow_alpha": 0.33
        }
    
    # Crear servicio
    draft_folder = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
    service = DraftService(draft_folder, profile)
    
    # Validar datos
    es_valido, mensaje = service.validar_datos_entrada(oraciones)
    
    if not es_valido:
        print(f"❌ Datos inválidos: {mensaje}")
        sys.exit(1)
    
    print(f"✅ {mensaje}")
    
    # PASO 4: Simular generación (dry-run)
    print(f"\n✅ PASO 4: Simulación de generación (DRY-RUN)")
    print("-" * 80)
    
    print(f"\n📋 Resumen de lo que se generaría:")
    print(f"  - Proyecto: {draft_name}")
    print(f"  - Oraciones: {len(oraciones)}")
    print(f"  - Palabras totales: {sum(len(o) for o in oraciones)}")
    
    # Simular overlap detection
    from core.subtitle_engine import SubtitleEngine
    engine = SubtitleEngine.__new__(SubtitleEngine)
    pares_overlap = engine._detectar_overlap_real(oraciones)
    print(f"  - Diálogos simultáneos detectados: {len(pares_overlap)}")
    
    # Simular división de bloques
    bloques = engine._dividir_en_bloques(oraciones, pares_overlap)
    print(f"  - Bloques generados (tras división): {len(bloques)}")
    
    max_palabras_en_bloque = max(len(b["palabras"]) for b in bloques) if bloques else 0
    print(f"  - Máximo de palabras por bloque: {max_palabras_en_bloque}")
    
    print(f"\n✅ SIMULACIÓN COMPLETADA EXITOSAMENTE")
    print(f"\n💡 Próximos pasos:")
    print(f"   1. Verificar que CapCut esté CERRADO")
    print(f"   2. Ejecutar: python test_integration_real.py '{json_path}' '{draft_name}' --generate")
    print(f"   3. Abrir CapCut para ver los subtítulos generados")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

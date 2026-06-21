# =====================================================================
# Script para generar subtitulos estilo karaoke acumulativo (VERSION 5)
# =====================================================================
# QUE HACE: toma el auto-caption nativo de CapCut (lineas completas sin
# estilo) y lo convierte en subtitulos estilo karaoke acumulativo palabra
# por palabra, con zigzag centrado y estilo visual calibrado.
#
# VERSION 5: parametros actualizados con datos reales extraidos de los
# drafts "tiggo 4" y "arrizzo 8" (junio 2026).
# =====================================================================

import json
import os
import sys
from pathlib import Path
from core.learning_engine import LearningEngine
from core.capcut_engine import CapcutEngine

def main():
    print("="*60)
    print("GENERADOR DE SUBTITULOS - KARAOKE ACUMULATIVO v5")
    print("="*60)
    
    # Inicializar motores
    learning_engine = LearningEngine()
    capcut_engine = CapcutEngine(learning_engine)
    
    # Listar proyectos disponibles
    proyectos = capcut_engine.list_projects()
    
    if not proyectos:
        print("❌ No se encontraron proyectos en CapCut.")
        print(f"Verifica la carpeta: {capcut_engine.get_drafts_folder()}")
        return
    
    print(f"\n✅ Se encontraron {len(proyectos)} proyectos:")
    for i, proj in enumerate(proyectos, 1):
        print(f"  {i}. {proj}")
    
    # Seleccionar proyecto
    while True:
        try:
            idx = int(input("\nSelecciona el número del proyecto: ")) - 1
            if 0 <= idx < len(proyectos):
                proyecto_seleccionado = proyectos[idx]
                break
            else:
                print("❌ Número inválido. Intenta de nuevo.")
        except ValueError:
            print("❌ Ingresa un número válido.")
    
    print(f"\n📽️  Proyecto seleccionado: {proyecto_seleccionado}")
    
    # Sugerir ajustes de formato
    print("\n📊 Analizando proyecto...")
    sugerencias = capcut_engine.suggest_format_adjustments(proyecto_seleccionado)
    
    if "error" in sugerencias:
        print(f"❌ Error: {sugerencias['error']}")
        return
    
    print(f"  - Oraciones detectadas: {sugerencias['total_sentences']}")
    print(f"  - Total de palabras: {sugerencias['total_words']}")
    print(f"  - Palabra más larga: {sugerencias['longest_word']} caracteres")
    print(f"  - Palabra más corta: {sugerencias['shortest_word']} caracteres")
    print(f"  - Promedio por oración: {sugerencias['avg_sentence_length']:.1f} palabras")
    
    print("\n⚙️  Configuración actual:")
    print(f"  - Escala: {sugerencias['current_scale']}")
    print(f"  - Ancho por carácter: {sugerencias['current_char_width']}")
    
    # Preguntar si continuar
    respuesta = input("\n¿Generar subtítulos con esta configuración? (s/n): ")
    
    if respuesta.lower() != 's':
        print("\n❌ Operación cancelada.")
        return
    
    # Generar subtítulos
    print("\n⏳ Generando subtítulos...")
    resultado = capcut_engine.generate_subtitles_for_project(
        proyecto_seleccionado,
        track_name="AUTO_subtitles",
        dry_run=False
    )
    
    if "error" in resultado:
        print(f"❌ Error: {resultado['error']}")
    else:
        print("\n✅ ¡Subtítulos generados exitosamente!")
        print(f"  - Palabras procesadas: {resultado['total_words']}")
        print(f"  - Bloques creados: {resultado['total_blocks']}")
        print(f"  - Diálogos simultáneos detectados: {resultado['simultaneous_dialogs']}")
        print(f"  - Track creado: {resultado['track_created']}")
        print("\n💡 Abre el proyecto en CapCut para ver el resultado.")
        
        # Registrar proyecto
        learning_engine.register_project(
            proyecto_seleccionado,
            {
                "track_name": "AUTO_subtitles",
                "total_words": resultado['total_words'],
                "settings_version": learning_engine.profile["version"]
            }
        )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operación interrumpida por el usuario.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

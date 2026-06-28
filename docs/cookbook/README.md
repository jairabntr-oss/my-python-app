# Cookbook — Sistema de subtítulos karaoke para CapCut

Esta carpeta es el punto de entrada para CUALQUIER sesión nueva (de
cualquier IA: Claude, ChatGPT, Cursor, lo que sea) que vaya a tocar este
proyecto. Leer en este orden:

1. **`notas_y_gotchas.md`** — leer SIEMPRE primero. Lista de bugs reales
   ya encontrados y resueltos, para no perder tiempo redescubriéndolos.
2. Después, la receta específica de lo que se necesita hacer:
   - **`generar_subtitulos.md`** — primera generación de subtítulos
     karaoke sobre un draft con auto-caption nativo.
   - **`limpiar_tracks_viejos.md`** — antes de regenerar sobre un draft
     que ya tiene una corrida anterior.
   - **`agregar_clicks.md`** — clicks de audio sincronizados (dos
     variantes: con auto-caption disponible, o reconstruyendo desde
     subtítulos ya editados a mano).

## Flujo tipico completo (de punta a punta)

1. CapCut: importar video, correr auto-caption nativo (Reconocimiento de voz)
2. [si es una REGENERACION] python limpiar_tracks_subtitulos.py "nombre draft"
3. python generar_subtitulos_baic_v5.py   (elegir el draft del menu)
4. Abrir CapCut, revisar visualmente, ajustar a mano si hace falta
5. python agregar_clicks_<draft>.py   (variante A o B segun si se toco el video)
6. Abrir CapCut, revisar audio

## Arquitectura (mapa rapido de archivos reales)

core/
  capcut_engine.py    - orquesta el pipeline
  subtitle_engine.py  - motor real de zigzag/colision/render/timing
  click_engine.py     - clicks de audio (ya resueltos sus bugs historicos)
  learning_engine.py  - perfil de estilo persistente (config/user_profile.json)
  draft_manager.py    - analisis/extraccion de drafts
  cleaner.py          - limpieza de tracks residuales (prefijo VIEJO AUTO_pos_N,
                        no conoce AUTO_sub_*, ver notas_y_gotchas.md)
utils/
  extract_autocaption.py - extractor unificado
  helpers.py              - utilidades compartidas
services/, ui/  - segunda ruta de uso (interfaz grafica), config separado
                  (settings.json en vez de user_profile.json)

Dos formas de generar subtitulos, mismo motor (SubtitleEngine), configs
de entrada DISTINTOS - ver notas_y_gotchas.md.

## Convencion de nombres de drafts en CapCut

Los proyectos derivados de un video mas largo (cortado en clips) usan el
patron "<nombre original> - <nombre clip>", ej. "entrv senores - clip1_serge".
Importa porque varios scripts necesitan el nombre EXACTO de la carpeta.

## Como verificar cualquier resultado, sin abrir CapCut

copy "C:\Users\<usuario>\AppData\Local\CapCut\User Data\Projects\<nombre_draft>\draft_content.json" "$env:USERPROFILE\Desktop\verificar.json"

# Receta: Generar subtítulos karaoke desde cero

## Cuándo usar esta receta

El draft de CapCut tiene auto-caption nativo (líneas completas, generadas
por CapCut, sin estilo) y todavía NO se generaron subtítulos karaoke con
este sistema. Es la receta de arranque para cualquier video nuevo.

**Cómo confirmar que aplica**: en el draft, debe existir un track de texto
con `recognize_task_id` poblado en sus materiales (eso es la marca real de
auto-caption nativo, no texto editado a mano). Si no hay ningún track así,
hay que correr primero el auto-caption en CapCut (Reconocimiento de voz).

## Comando

```powershell
python generar_subtitulos_baic_v5.py
```

Es interactivo: lista los drafts disponibles en tu carpeta de CapCut,
elegís el número, te muestra un resumen (oraciones detectadas, palabras,
palabra más larga/corta) y te pide confirmar con `s` antes de escribir
nada.

## Qué hace internamente (para quien necesite tocar el código)

```
generar_subtitulos_baic_v5.py
  -> CapcutEngine.generate_subtitles_for_project(project_name, track_name="AUTO_subtitles")
       -> CapcutEngine.extract_captions_from_draft()
            -> AutocaptionExtractor.extract()   (utils/extract_autocaption.py)
                 -> DraftManager.oraciones_desde_json()  (camino principal)
                 -> fallback: arrays paralelos + detección de unidad us/ms/s
       -> CapcutEngine.detect_simultaneous_dialog()   (overlap real >=150ms)
       -> CapcutEngine.split_long_sentence()          (máx 5 palabras/bloque)
       -> SubtitleEngine.generate()                   (core/subtitle_engine.py)
            -> _detectar_overlap_real()
            -> _dividir_en_bloques()
            -> _calcular_posiciones()    <- zigzag, colisión, zona Y
            -> _crear_segmentos()        <- timing acumulativo, escribe el draft
            -> _inyectar_estilo_avanzado()  <- sombra, fuente Poppins-Bold
```

El track resultante se llama `AUTO_sub_N` (uno por "zona" de posicionamiento
consecutiva), **no** `AUTO_subtitles` como dice el parámetro — el nombre
real está hardcodeado en `SubtitleEngine.TRACK_PREFIX`. Esto es una
inconsistencia conocida, ver `docs/cookbook/notas_y_gotchas.md`.

## Verificación de éxito (antes de abrir CapCut)

El bug más insidioso de esta receta es que el script puede reportar
"✅ generado exitosamente" con números reales (palabras, bloques) **sin
que el archivo en disco tenga nada nuevo** — pasó por un caché de Python
viejo (`__pycache__`), no por el código en sí. Por eso, antes de abrir
CapCut, conviene verificar el resultado real:

```powershell
copy "C:\Users\<usuario>\AppData\Local\CapCut\User Data\Projects\<nombre_draft>\draft_content.json" "$env:USERPROFILE\Desktop\verificar.json"
```

Y confirmar manualmente (o pedirle a la IA que lo confirme) que aparecen
tracks `AUTO_sub_0`, `AUTO_sub_1`, etc. con segmentos reales — no solo el
auto-caption original.

## Antes de correr, si ya se generó una vez sobre el mismo draft

Si el draft ya tiene tracks `AUTO_sub_*` de una corrida anterior (por
ejemplo, porque se quiere regenerar con otra calibración), hay que
limpiarlos primero — ver `docs/cookbook/limpiar_tracks_viejos.md`. Si no se
limpia, los tracks viejos quedan mezclados con los nuevos en pantalla.

## Después de generar: limpiar caché SIEMPRE que se haya tocado código

Si en la misma sesión se editó algún archivo de `core/` (por ejemplo
`subtitle_engine.py`), correr esto ANTES de generar — Python puede seguir
usando bytecode compilado viejo si el caché no se invalida bien:

```powershell
Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
```

## Ejemplo real (clip2_fantastica, sesión de referencia)

```
✅ Se encontraron 54 proyectos: ...
Selecciona el número del proyecto: 34
📽️  Proyecto seleccionado: entrv señores - clip2_fantastica
📊 Analizando proyecto...
  - Oraciones detectadas: 42
  - Total de palabras: 206
  - Palabra más larga: 11 caracteres
  - Palabra más corta: 1 caracteres
  - Promedio por oración: 4.9 palabras
¿Generar subtítulos con esta configuración? (s/n): s
⏳ Generando subtítulos...
✅ ¡Subtítulos generados exitosamente!
  - Palabras procesadas: 206
  - Bloques creados: 56
  - Diálogos simultáneos detectados: 0
  - Track creado: AUTO_subtitles
```

Resultado real en disco (verificado): 5 tracks `AUTO_sub_0` a `AUTO_sub_4`
con 56+51+43+36+20 = 206 segmentos.

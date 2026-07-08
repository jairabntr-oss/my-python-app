# Análisis y mejoras del repo `my-python-app`

Resumen de lo que encontré al revisar el repo y lo que cambié. Mantengo tu
formato (módulos `core/ services/ utils/ ui/ config/ tests/`, comentarios en
español, docstrings explicando el "por qué"). 27 tests pasan (22 tuyos + 5
nuevos de regresión).

## 1. Bugs críticos corregidos (rompían funcionalidad)

### 1.1 La CLI no extraía NADA de los drafts
`CapcutEngine._parse_captions_from_content` recorría
`track["clips"][...]["words"]` con campos `startTime` / `endTime`. Esa
estructura **no existe** en el `draft_content.json` real de CapCut: los
segmentos viven en `track["segments"]` y las palabras del auto-caption están
dentro de `materials.texts[].content` (un JSON string con `words[]` en
microsegundos). Resultado: la CLI siempre devolvía `[]` y mostraba
"No se encontraron captions".

**Arreglo:** `extract_captions_from_draft` ahora delega en
`AutocaptionExtractor` (el parser unificado que ya tenías y que está probado
con datos reales). Una sola fuente de verdad para parsear, en vez de tres.

### 1.2 La CLI construía el motor con argumentos equivocados
`generate_subtitles_for_project` hacía
`SubtitleEngine(carpeta, nombre, profile)` pero el constructor es
`SubtitleEngine(script, profile)`. Le pasaba la carpeta como `script` y el
nombre como `profile`.

**Arreglo:** ahora usa el factory correcto `SubtitleEngine.from_draft(...)`,
que carga el draft con `load_template()` (además respeta el "Error #1" del
handoff: nada de `duplicate_as_template`).

Con 1.1 + 1.2, el script `generar_subtitulos_baic_v5.py` vuelve a funcionar.

## 2. Inconsistencias que dejaban resultados distintos según el camino

### 2.1 Escala del texto: 1.67 vs 3.037 (≈ doble de tamaño)
- Ruta **UI** (`settings.json`): `scale = 3.037`
- Ruta **CLI** (`user_profile.json` / default de `LearningEngine`): `scale = 1.67`

Es decir, el mismo video salía con texto de tamaño muy distinto según
generaras desde la UI o desde la CLI.

**Arreglo:** unifiqué todo en **3.037 (~303%)**, la calibración validada del
proyecto original (handoff "entrv fede baic"). Quedó igual en `settings.json`,
`user_profile.json`, el default de `LearningEngine` y `default_profile.json`.

> ❓ **Decisión que tenés que confirmar:** tu `ANALISIS_FORMATO_ESTILO.md`
> midió `1.67` para los videos nuevos "tiggo 4" / "arrizzo 8". El handoff
> validó `3.037` para "entrv fede baic". Son videos distintos. Elegí 3.037
> para no cambiar el comportamiento de la UI (que es el camino principal). Si
> tu estilo manual actual es el de 1.67, cambialo en los **tres** lugares de
> arriba a la vez. Lo dejé documentado en `ANALISIS_FORMATO_ESTILO.md` y el
> `README.md`.

### 2.2 Umbral de overlap `>` vs `>=`
`CapcutEngine.detect_simultaneous_dialog` usaba `>` y
`SubtitleEngine._detectar_overlap_real` usaba `>=`. En el caso borde (overlap
exactamente igual al umbral) discrepaban. Lo dejé en `>=` en los dos.

## 3. Higiene del repo
- **`LICENSE`**: el README lo referenciaba pero no existía. Agregué MIT.
- **`__pycache__` versionado**: había 19 `.pyc` trackeados en git (de antes de
  que existiera el `.gitignore`). Los saqué del control de versiones
  (`git rm --cached`). El `.gitignore` ya estaba bien.
- **`config/default_profile.json`**: tenía contenido genérico sin relación con
  el proyecto (`username/theme/language/notifications`) y no lo usaba nadie. Lo
  reescribí como plantilla coherente del perfil de estilo por defecto
  (sirve de referencia/reset).
- **`core/logger.py`**: `get_logger()` agregaba handlers nuevos en cada llamada
  con el mismo nombre → líneas de log duplicadas. Ahora es idempotente.
- **Imports muertos** quitados (`hashlib`, `AnalysisError`, `List`, `Dict`,
  `Path` según el archivo). `pyflakes` queda limpio.

## 4. Tests nuevos (`tests/test_capcut_engine.py`)
5 tests de regresión que fijan los arreglos de arriba para que no se rompan
otra vez:
- la extracción encuentra el auto-caption real,
- engine y extractor coinciden,
- el umbral de overlap es `>=`,
- `generate_subtitles_for_project` usa el factory (no el constructor),
- `from_draft` existe como classmethod.

## 5. Lo que NO toqué (a propósito)
- El motor de posicionamiento (zigzag/anti-colisión) y el de clicks: funcionan
  y están cubiertos por tus tests.
- La duplicación de lógica entre `CapcutEngine` (`calculate_word_positions`,
  etc.) y `SubtitleEngine`: la dejé porque al enrutar la generación real por
  `SubtitleEngine` esa duplicación ya no causa bugs. Si querés, en una próxima
  pasada se puede borrar el código muerto de `CapcutEngine` y dejar solo el
  delegado, pero eso es refactor, no arreglo.

## Cómo aplicar estos cambios a tu GitHub
Opción A (recomendada): copiá los archivos del zip sobre tu copia local y
hacé commit/push normal.

Opción B (patch): en un clon limpio,
```
git apply mejoras_my-python-app.patch    # o: git am < mejoras_my-python-app.patch
```

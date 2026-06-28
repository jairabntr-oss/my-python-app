# Notas y gotchas — leer ANTES de tocar código de este repo

Esta es la lista acumulada de bugs reales encontrados en sesiones
anteriores, con su causa y solución. El objetivo es que cualquier sesión
nueva (de cualquier IA) no tenga que volver a descubrir esto de cero.

## 1. Caché de Python (`__pycache__`) puede esconder fixes ya aplicados

**Síntoma**: se edita `core/subtitle_engine.py` (o cualquier `.py`), se
confirma con `Get-FileHash` que el archivo en disco es el correcto, pero
al correr el generador el comportamiento sigue siendo el VIEJO.

**Causa**: una carpeta `__pycache__` con bytecode compilado de una versión
anterior no se invalidó sola (puede pasar con relojes de sistema
desincronizados o copias de archivo que no actualizan bien el `mtime`).

**Solución**: correr esto SIEMPRE después de reemplazar cualquier `.py` de
`core/` o `utils/`, antes de generar nada:

```powershell
Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
```

## 2. Verificar SIEMPRE el hash del archivo real antes de editarlo "a ciegas"

El usuario subió en algún momento una versión de `subtitle_engine.py` que
ya estaba desactualizada respecto a lo que tenía en disco real (le faltaba
todo un sistema de `factor_reduccion` para palabras largas que ya existía
en el repo real). Si una sesión edita sobre una copia vieja sin saberlo,
genera un archivo que "pierde" mejoras reales ya aplicadas.

**Antes de editar cualquier archivo de código que el usuario suba**: pedir
que confirme el hash real (`Get-FileHash -Algorithm SHA256`) del archivo
en su repo, y compararlo contra lo que se está editando.

## 3. Bajar archivos del chat falla en silencio, frecuentemente

El usuario varias veces creyó haber "descargado" un archivo que en
realidad: (a) nunca se guardó, (b) se guardó con un nombre distinto
(`subtitle_engine (1).py`), o (c) quedó en una carpeta distinta a la
esperada (la raíz del repo en vez de Descargas).

**Mitigación**: después de cualquier reemplazo de archivo, confirmar
SIEMPRE con `Get-FileHash` antes de asumir que funcionó. No avanzar al
siguiente paso sin esa confirmación.

## 4. `git am` puede quedar a medias y no avisar claro

En una sesión, `git status` reveló "You are in the middle of an am
session" sin que el usuario supiera cómo se llegó a ese estado. Mientras
el repo está así, cualquier commit/push puede comportarse raro.

**Regla**: si se va a tocar git, correr `git status` PRIMERO, siempre,
antes de cualquier otra operación. Si aparece cualquier mensaje de
operación a medias (`am`, `rebase`, `merge`), resolver eso explícitamente
(`git am --abort`, etc.) antes de seguir con cualquier otra cosa.

**No asumir** que el usuario va a mencionar espontáneamente que el repo
está en un estado raro — a veces no lo notan.

## 5. El prefijo de tracks de subtítulos NO es `AUTO_subtitles`

`generar_subtitulos_baic_v5.py` pasa `track_name="AUTO_subtitles"` a
`generate_subtitles_for_project()`, pero ese parámetro **no se usa
realmente** para nombrar el track final — `SubtitleEngine.TRACK_PREFIX =
"AUTO_sub_"` es el prefijo real, y cada "zona" de posicionamiento
consecutiva genera su propio track (`AUTO_sub_0`, `AUTO_sub_1`, etc.). Si
se busca el track por el nombre que dice el mensaje de éxito, no se va a
encontrar nada.

## 6. La posición Y de los subtítulos es GLOBAL, no por-proyecto

En `core/subtitle_engine.py`, `_calcular_posiciones` tiene hardcodeado
`y_zona_min, y_zona_max = -0.45, -0.05` para bloques normales (sin
diálogo simultáneo). Este valor se cambió en una sesión específicamente
para el video "entrv señores" (el usuario quería el texto a la altura de
los pantalones, no centrado), pero **el cambio afecta a CUALQUIER draft**
que se procese desde ese momento en adelante — no es selectivo por
proyecto.

**Antes de generar subtítulos para un proyecto nuevo**: confirmar con el
usuario si quiere esa misma posición baja, o si hay que revertir a
centrado (`-0.4, 0.4`), o si conviene parametrizar esto de una vez (ver
sección de mejoras pendientes más abajo).

## 7. Valores de calibración visual — no cambiarlos sin medir empíricamente

Estos tres valores están relacionados entre sí y calibrados contra datos
reales de "entrv fede baic" (el draft que el usuario ya aprobó
visualmente). Si se cambia uno, hay que revisar los otros dos:

| Constante | Valor actual | Por qué |
|---|---|---|
| `min_dist_y` | 0.11 | Medido contra los pares de palabras simultáneas MÁS CERCANOS en un draft ya aprobado — con dx≈0, el dy real nunca bajaba de ~0.11 |
| `PASO_Y_CORTO` | 0.12 | Debe ser >= `min_dist_y`, si no el avance normal entre palabras ya dispara colisiones falsas |
| `PASO_Y_LARGO` | 0.16 | Idem, para palabras de 8+ letras |

Un pedido anterior de "achicar distancia entre líneas" bajó
`PASO_Y_CORTO/LARGO` a 0.045/0.09 sin tocar `min_dist_y` (que en ese
momento era 0.04) — el desbalance hizo que el sistema anti-colisión se
disparara en casi cada palabra, amontonando todo el texto en una esquina
en vez de usar el rango disponible. Síntoma real visto: capturas de
pantalla con texto apelmazado y muy arriba.

**Si el usuario pide "más/menos separación entre palabras" de nuevo**:
calcular el nuevo valor y verificar matemáticamente (simulando el cálculo
con Python puro, sin necesidad de CapCut) que el resultado no rompa el
balance — no cambiar un solo número a ciegas.

## 8. Fragmentar video/audio que cruza un punto de corte: SIEMPRE generar 2 fragmentos

Bug encontrado en scripts de corte ad-hoc (no en `core/`, en scripts
puntuales por proyecto): cuando un tramo a eliminar cae estrictamente EN
MEDIO de un único segmento de video/audio más largo, hay que generar DOS
fragmentos nuevos (antes y después del corte), cada uno con su propio
`id` nuevo — no un `if/else` que solo guarda un lado. Si se guarda solo un
lado, se pierde contenido real y todo lo posterior queda mal desplazado
(huecos y saltos hacia atrás en el tiempo).

## 9. IDs de segmento: SIEMPRE regenerar, nunca reusar el original al fragmentar

Relacionado con el punto anterior: si un mismo segmento original se
fragmenta en dos (por cruzar un límite de corte), AMBOS fragmentos
necesitan un `id` nuevo (UUID), no heredar el `id` original — si dos
segmentos distintos en el mismo track comparten `id`, CapCut descarta uno
en silencio al abrir el draft (sin avisar de ningún error).

## 10. Extensión de duración de bloques karaoke: solo si están en la misma zona

Fix aplicado en `_crear_segmentos`: cada bloque de texto se extiende para
durar hasta justo antes de que arranque el bloque siguiente (con margen de
~16ms), para que un bloque residual chico (1-2 palabras tras dividir una
oración larga) no quede con una duración casi imperceptible. **Pero** esto
solo debe aplicarse cuando el bloque siguiente está en la MISMA zona de
pantalla — si el siguiente es parte de un diálogo simultáneo en la zona
opuesta (arriba/abajo), extender uno le "robaría" tiempo de pantalla al
otro sin necesidad real.

## Deuda técnica conocida (no son bugs, son mejoras pendientes)

- **`core/cleaner.py` no conoce el prefijo `AUTO_sub_`** — solo el viejo
  `AUTO_pos_N`. Por eso existe `limpiar_tracks_subtitulos.py` como script
  separado en la raíz. Candidato: fusionar como método nuevo dentro de
  `Cleaner`.
- **3 scripts de clicks casi idénticos** (`agregar_clicks_clip1_serge.py`,
  `agregar_clicks_clip2_fantastica.py`, `agregar_clicks_x55_plus_urg.py`),
  solo difieren en `DRAFT_NAME`. Candidato: un solo script parametrizable
  por argumento de línea de comando.
- **Dos rutas de configuración paralelas** (CLI usa
  `config/user_profile.json` vía `LearningEngine`; la UI usa
  `settings.json` vía `DraftService`). Mismo motor (`SubtitleEngine`),
  configs separados — riesgo real de que se desincronicen sin que nada
  avise. No es urgente si el usuario no usa la UI activamente; confirmar
  con él antes de invertir tiempo en unificar esto.
- **Posición Y hardcodeada y global** (ver punto 6 arriba) — debería ser
  un parámetro por proyecto, no una constante de clase.
- **Archivos sueltos en la raíz del repo a revisar/limpiar**: `copy`,
  `tatus` (parecen restos de comandos de shell pegados mal y commiteados
  por error), y varios `.patch` sueltos
  (`arreglo_offset_y_limpieza_nativo.patch`,
  `arreglo_posiciones_amontonadas.patch`, `arreglo_sombra_y_fuente.patch`,
  `arreglos_subtilearn.patch`). **Antes de borrar los `.patch`**, revisar
  su contenido — podrían documentar un fix que todavía no está aplicado en
  el código actual.

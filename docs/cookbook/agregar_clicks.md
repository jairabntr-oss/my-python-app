# Receta: Agregar clicks de audio sincronizados

## Cuándo usar esta receta

Después de tener los subtítulos karaoke ya generados (y, si se editaron a
mano, ya ajustados) sobre un draft. Agrega un sonido de "click" corto al
inicio y al fin de cada bloque visual de texto.

## Hay DOS variantes — elegir según el caso

### Variante A: el auto-caption original todavía existe en el draft

Es el caso normal: se generaron los subtítulos y no se tocó el video/audio
del draft (como mucho se ajustaron posiciones de texto a mano, sin cortar
nada). `ClickEngine` puede usar `AutocaptionExtractor` para releer las
oraciones reales con sus timestamps originales.

Ejemplo de referencia: `agregar_clicks_arrizzo8.py` (ya en el repo).

```python
from utils.extract_autocaption import AutocaptionExtractor
from core.cleaner import Cleaner
from core.click_engine import ClickEngine
import pycapcut as cc

oraciones, stats = AutocaptionExtractor.extract(str(json_path))
# ... cargar el script, limpiar tracks de audio residuales si hace falta ...
click_engine = ClickEngine(script, ruta_sonido)
resultado = click_engine.generate(oraciones, modo="2_por_oracion")
```

### Variante B: el video/audio fue editado/cortado a mano DESPUÉS de generar subtítulos

Caso real frecuente: se generaron los subtítulos, después se cortó video
o se reordenaron bloques a mano en CapCut. El auto-caption original puede
ya no existir, o sus timestamps ya no corresponden al timeline actual.

**No usar `AutocaptionExtractor` en este caso** — daría timestamps viejos
o fallaría directamente. En su lugar, reconstruir los "bloques visuales"
directamente de los segmentos de texto YA EDITADOS que están en el draft
ahora mismo:

```python
def construir_bloques_visuales(json_path):
    """Agrupa los segmentos de texto YA EXISTENTES en el draft (editados a
    mano) en bloques visuales reales. Un bloque nuevo arranca cuando una
    palabra empieza en o después del momento en que el bloque anterior deja
    de mostrarse en pantalla."""
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
            content = json.loads(mat["content"])
            texto = (content.get("text") or "").strip()
            if not texto:
                continue
            tr = seg["target_timerange"]
            palabras.append({"word": texto, "start_us": tr["start"], "end_us": tr["start"] + tr["duration"]})
    palabras.sort(key=lambda p: p["start_us"])

    bloques, bloque_actual, fin_max_bloque = [], [], None
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
```

El resultado (`bloques`) tiene exactamente el mismo formato que las
"oraciones" de `AutocaptionExtractor`, así que se le pasa igual a
`ClickEngine.generate()`:

```python
bloques = construir_bloques_visuales(str(json_path))
click_engine = ClickEngine(script, ruta_sonido)
resultado = click_engine.generate(bloques, modo="2_por_oracion")
```

`ClickEngine` en sí **no se toca** — ya tiene resueltos los dos bugs
históricos (registro explícito del material de audio con
`script.add_material()`, y 2 clicks por bloque en vez de 3). Ver
`core/click_engine.py`.

Ejemplos de referencia ya en el repo:
`agregar_clicks_clip1_serge.py`, `agregar_clicks_clip2_fantastica.py`,
`agregar_clicks_x55_plus_urg.py` — los tres son copias casi idénticas
salvo el `DRAFT_NAME`. (Candidato a refactor, ver
`docs/cookbook/notas_y_gotchas.md`.)

## Verificación previa (antes de correr, sin tocar el draft)

Conviene confirmar que la cantidad de bloques/clicks estimados tiene
sentido, y que no haya casos límite raros (dos clicks tan pegados que se
pisarían):

```python
timestamps = set()
for b in bloques:
    n = len(b)
    for idx in (0, n - 1):
        timestamps.add(int(b[idx]["start_us"]))
timestamps = sorted(timestamps)

for i in range(len(timestamps) - 1):
    gap = timestamps[i + 1] - timestamps[i]
    if gap < 50_000:  # menos de 50ms
        print(f"Gap chico: {timestamps[i]/1e6:.3f}s -> {timestamps[i+1]/1e6:.3f}s")
```

Casos con gaps menores a 50ms no son un error — `ClickEngine` ya recorta
la duración del click para que no se pisen — pero vale la pena saber de
antemano que van a sonar muy juntos.

## Verificación de "ya existe un track de audio con ese nombre"

Antes de correr, chequear que no haya ya un track `AUTO_clicks` (para no
duplicar si se corre dos veces sobre el mismo draft):

```python
for t in data["tracks"]:
    if t["type"] == "audio":
        print(t["name"], len(t["segments"]))
```

## Requisito: `assets/click_sonido.mp3`

Ya está commiteado en el repo — no hace falta volver a pedírselo al
usuario en sesiones nuevas. Si por algún motivo falta, el usuario lo tiene
históricamente en su Escritorio de Windows.

## Ejemplo real (clip1_serge, variante B, sesión de referencia)

```
Bloques visuales: 30
Palabras: 108
Clicks estimados (2 por bloque): 60
```
Resultado real tras correr: 58 timestamps únicos (2 se fusionaron por
coincidir exactamente), 1 caso de gap chico (33ms) entre dos bloques
consecutivos de habla muy rápida — aceptado como límite conocido, no se
intentó forzar más separación porque hubiera requerido inventar tiempo que
no corresponde al audio real.

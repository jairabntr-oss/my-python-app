# =====================================================================
# Reordena 4 bloques completos (video+audio+texto, TAL CUAL estan, sin
# tocar el contenido/posicion de cada subtitulo ya editado a mano) del
# draft "mariaaa baic".
# =====================================================================
# Orden ACTUAL:  A (intro+specs) -> B (precio) -> C (negociacion/cierre) -> D (auto por dentro/defectos/comodidad)
# Orden NUEVO:   A -> D -> B -> C
#
# Bloque A: 0.000s   - 35.500s  (se mantiene en su lugar)
# Bloque B: 35.500s  - 38.033s  (precio - se mueve al final, antes de C)
# Bloque C: 38.033s  - 43.933s  (negociacion + 'listo lo voy a comprar' - CIERRE final)
#           NOTA: ajustado de 43.300s a 43.933s (borde real de un clip
#           de video que iba de 42.900s a 43.933s y cruzaba el corte
#           original en el medio - decision del usuario: mover el
#           limite al borde real del clip en vez de fragmentarlo).
# Bloque D: 43.933s  - 79.700s  (auto por dentro, defectos, comodidad - se mueve justo despues de A)
# =====================================================================

import json
import copy

RUTA_JSON_ORIGINAL = "maria_v2_con_ediciones.json"
RUTA_JSON_SALIDA = "draft_content_MARIA_REORDENADO.json"

# (nombre, inicio_us, fin_us) en el timeline ACTUAL
BLOQUE_A = ("A_intro_specs",        0,              35_500_000)
BLOQUE_B = ("B_precio",             35_500_000,     38_033_000)
BLOQUE_C = ("C_negociacion_cierre", 38_033_000,     43_933_000)
BLOQUE_D = ("D_auto_defectos",      43_933_000,     79_700_000)

# Orden NUEVO: A, D, B, C
ORDEN_NUEVO = [BLOQUE_A, BLOQUE_D, BLOQUE_B, BLOQUE_C]


def extraer_segmentos_del_rango(track, ini_us, fin_us):
    """Devuelve los segmentos de un track cuyo target_timerange cae
    DENTRO del rango [ini_us, fin_us) (con tolerancia de 1ms en los
    bordes, para no perder segmentos por redondeo)."""
    extraidos = []
    for seg in track.get("segments", []):
        tr = seg.get("target_timerange")
        if tr is None:
            continue
        s_ini = tr["start"]
        if ini_us - 1000 <= s_ini < fin_us - 1000:
            extraidos.append(seg)
    return extraidos


def main():
    with open(RUTA_JSON_ORIGINAL, "r", encoding="utf-8") as f:
        data = json.load(f)

    duracion_original = data["duration"]
    print(f"Duracion original: {duracion_original/1e6:.3f}s")

    # Verificacion: la suma de los 4 bloques debe cubrir TODO el
    # timeline original sin huecos ni overlaps entre ellos.
    bloques_ordenados_por_tiempo = sorted(ORDEN_NUEVO, key=lambda b: b[1])
    prev_fin = 0
    for nombre, ini, fin in bloques_ordenados_por_tiempo:
        if ini != prev_fin:
            print(f"AVISO: hueco/overlap entre bloques en {prev_fin/1e6:.3f}s -> {ini/1e6:.3f}s")
        prev_fin = fin
    if prev_fin != duracion_original:
        print(f"AVISO: el ultimo bloque termina en {prev_fin/1e6:.3f}s pero la duracion total es {duracion_original/1e6:.3f}s")

    # Calcular el nuevo offset de inicio de cada bloque, en el ORDEN NUEVO
    offset_nuevo = {}
    acumulado = 0
    for nombre, ini, fin in ORDEN_NUEVO:
        offset_nuevo[nombre] = acumulado
        acumulado += (fin - ini)
    nueva_duracion_total = acumulado
    print(f"Nueva duracion total: {nueva_duracion_total/1e6:.3f}s (debe ser igual a la original)")

    nuevos_tracks = []
    for track in data.get("tracks", []):
        nuevos_segmentos = []
        for nombre, ini_us, fin_us in ORDEN_NUEVO:
            segs_bloque = extraer_segmentos_del_rango(track, ini_us, fin_us)
            shift = offset_nuevo[nombre] - ini_us
            for seg in segs_bloque:
                nuevo_seg = copy.deepcopy(seg)
                tr = nuevo_seg["target_timerange"]
                nuevo_seg["target_timerange"] = {
                    "start": tr["start"] + shift,
                    "duration": tr["duration"],
                }
                # render_timerange: solo desplazar si tenia duracion real
                # (no tocar el valor "sin usar" de 0, mismo criterio ya
                # validado en los scripts anteriores)
                rr = nuevo_seg.get("render_timerange")
                if rr is not None and rr.get("duration", 0) > 0:
                    rr["start"] = rr.get("start", 0) + shift
                nuevos_segmentos.append(nuevo_seg)

        nuevo_track = copy.deepcopy(track)
        nuevo_track["segments"] = nuevos_segmentos
        nuevos_tracks.append(nuevo_track)

    data["tracks"] = nuevos_tracks
    data["duration"] = nueva_duracion_total

    with open(RUTA_JSON_SALIDA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print()
    print(f"Listo. Archivo nuevo escrito en: {RUTA_JSON_SALIDA}")
    total_segs = sum(len(t["segments"]) for t in nuevos_tracks)
    print(f"Cantidad de tracks: {len(nuevos_tracks)} | Total de segmentos: {total_segs}")


if __name__ == "__main__":
    main()

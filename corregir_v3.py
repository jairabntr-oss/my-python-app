# =====================================================================
# Script v3 - Correcciones sobre el video ya editado a mano
# =====================================================================
# Parte de FEDE_v3_REVISION_FINAL_81seg.json (80.67s, con el corte y el
# cartel ya aplicados + ediciones manuales del usuario encima) y aplica:
#
#   1. Quita el TEXTO superpuesto del titulo grafico ("Entrevista /
#      Lanzamiento / Arcfox") en 0.0s-0.3s. El video/audio de ese
#      instante NO se toca - sigue siendo el inicio real del hook
#      (confirmado con el usuario: la voz de Fede arranca ahi mismo).
#   2. Elimina el tramo 38.27s-43.10s ("no la uso mucho... a Bariloche,
#      eh, la verdad que") - pedido explicito del usuario, con el limite
#      ajustado a 43.10s (no 44.00s) para no partir la frase siguiente
#      ("si le metimos, le metimos, es grande").
#   3. Acelera TODO el resultado a 1.25x: cada segmento de video/audio
#      cambia su material 'speed' a 1.25 y su target_timerange se
#      acorta a duracion/1.25; el texto se recalcula proporcionalmente
#      para seguir sincronizado (no tiene 'speed' real, es solo
#      reposicionamiento de su target_timerange).
#
# El filtro blanco y negro del hook NO se aplica por script (decision
# explicita: el usuario lo agrega a mano en CapCut, mas seguro que
# fabricar a ciegas el material de efecto sin un effect_id real de
# CapCut).
# =====================================================================

import json
import copy
import uuid

# =====================================================================
# CONFIGURACION
# =====================================================================

RUTA_JSON_ORIGINAL = "FEDE_v3_REVISION_FINAL_81seg.json"
RUTA_JSON_SALIDA = "draft_content_V3_NUEVO.json"

FACTOR_VELOCIDAD = 1.25

# IDs de los 3 segmentos de TEXTO del titulo grafico a eliminar (el
# video/audio de ese mismo instante 0.0-0.3s NO se toca).
SEGMENT_IDS_TITULO_A_ELIMINAR = {
    "7EA50B59-014A-45A5-80F2-CE5A6DFF980C",  # "Entrevista"
    "769535CE-0675-4738-9E34-61B3D24087FE",  # "Lanzamiento"
    "A9F664BB-F60D-46B4-8FCD-0080297AED0F",  # "Arcfox"
}

# Tramo a eliminar (en microsegundos, sobre el timeline ACTUAL de
# FEDE_v3_REVISION_FINAL_81seg.json, antes de acelerar).
# AJUSTADO a los timestamps EXACTOS de las palabras (no valores
# redondeados a 38.27/43.10): la palabra "no" arranca en 38.2667s pero
# su target_timerange se extiende hasta 38.5667s (efecto karaoke
# acumulativo, varias palabras compartiendo el mismo fin de pantalla).
# Si el corte cae en medio de ese rango (como pasaba con 38.27s
# redondeado), genera un fragmento parcial en vez de excluir la palabra
# entera. Por eso el limite real usado es el INICIO exacto de "no"
# (38.266666s) y el FIN exacto de "que" (43.099999s, ultima palabra
# antes de "si le metimos").
ELIMINAR_INICIO_US = 38_266_666  # inicio exacto de la palabra "no"
ELIMINAR_FIN_US = 43_100_000     # fin exacto de la palabra "que" (antes de "si")


def nuevo_id():
    return str(uuid.uuid4())


def recortar_fuera_del_tramo(seg, eliminar_ini, eliminar_fin, offset_acumulado):
    """Dado un segmento con target_timerange, devuelve una lista de 0, 1
    o 2 nuevos segmentos: la(s) parte(s) que quedan FUERA del tramo
    [eliminar_ini, eliminar_fin), desplazadas por offset_acumulado para
    cerrar el hueco. Si el segmento cae completamente dentro del tramo a
    eliminar, devuelve lista vacia. Si lo cruza por un solo lado, recorta
    ese lado. Si el tramo a eliminar caeen medio del segmento (caso
    raro, no esperado aqui), lo partiria en dos - se maneja por si acaso.

    NOTA sobre el bug ya conocido: cada fragmento resultante recibe un
    id nuevo SIEMPRE (no solo cuando hay duplicacion), porque un mismo
    segmento original puede producir mas de un fragmento si cruza un
    limite - ver el bug de ids duplicados ya corregido en una vuelta
    anterior de este proyecto.
    """
    tr = seg["target_timerange"]
    ini, fin = tr["start"], tr["start"] + tr["duration"]

    resultados = []

    # Parte ANTES del tramo a eliminar
    if ini < eliminar_ini:
        fin_parte = min(fin, eliminar_ini)
        if fin_parte > ini:
            resultados.append((ini, fin_parte))

    # Parte DESPUES del tramo a eliminar
    if fin > eliminar_fin:
        ini_parte = max(ini, eliminar_fin)
        if fin > ini_parte:
            resultados.append((ini_parte, fin))

    # Si el segmento no toca el tramo a eliminar en absoluto, se conserva entero
    if not resultados and not (ini < eliminar_fin and fin > eliminar_ini):
        resultados.append((ini, fin))

    nuevos = []
    for ini_p, fin_p in resultados:
        dur_p = fin_p - ini_p
        nuevo_seg = copy.deepcopy(seg)
        nuevo_seg["id"] = nuevo_id()

        # Desplazamiento: todo lo que esta a partir de eliminar_fin se
        # corre hacia atras por (eliminar_fin - eliminar_ini), para
        # cerrar el hueco. Lo que esta antes de eliminar_ini no se
        # desplaza por este paso (offset_acumulado ya viene en 0 aqui,
        # se aplica un unico offset global mas adelante via shift simple).
        nuevo_target_start = ini_p - offset_acumulado
        nuevo_seg["target_timerange"] = {
            "start": nuevo_target_start,
            "duration": dur_p,
        }

        # source_timerange: si existe, recortar proporcionalmente el
        # lado que corresponda (solo relevante si dur_p != duracion
        # original, es decir, si este es un fragmento partido).
        sr = seg.get("source_timerange")
        if sr is not None:
            recorte_inicio = ini_p - ini  # cuanto se recorto del inicio
            nuevo_seg["source_timerange"] = {
                "start": sr["start"] + recorte_inicio,
                "duration": dur_p,
            }

        rr = seg.get("render_timerange")
        if rr is not None and rr.get("duration", 0) > 0:
            recorte_inicio = ini_p - ini
            nuevo_seg["render_timerange"] = {
                "start": rr.get("start", 0) + recorte_inicio,
                "duration": dur_p,
            }

        nuevos.append(nuevo_seg)

    return nuevos


def aplicar_eliminacion_tramo(data, eliminar_ini, eliminar_fin):
    """Recorre TODOS los tracks (video/audio/text) y elimina el tramo
    [eliminar_ini, eliminar_fin), cerrando el hueco (todo lo posterior
    se corre hacia atras por la duracion eliminada).

    Para texto, NO se fragmenta parcialmente: en el estilo karaoke
    acumulativo, varias palabras comparten el mismo target_timerange.end
    (el momento en que el BLOQUE entero deja de mostrarse), aunque cada
    palabra arranque (su 'start' real) en un instante distinto. Si se
    fragmentara por interseccion de rango como con video/audio, una
    palabra cuyo 'start' cae JUSTO ANTES del limite pero cuyo 'end'
    se extiende un poco dentro del tramo a eliminar quedaria partida en
    un fragmento residual sin sentido (caso real detectado: la palabra
    "no" quedando pegada despues del corte). Por eso, para texto, el
    criterio es: se descarta ENTERO si su 'start' cae dentro del tramo
    a eliminar; se conserva ENTERO (solo desplazado) si no.
    """
    duracion_eliminada = eliminar_fin - eliminar_ini

    for track in data.get("tracks", []):
        es_texto = track.get("type") == "text"
        nuevos_segmentos = []
        for seg in track.get("segments", []):
            tr = seg.get("target_timerange")
            if tr is None:
                nuevos_segmentos.append(seg)
                continue

            ini, fin = tr["start"], tr["start"] + tr["duration"]

            if es_texto:
                # Regla simplificada para texto: decide solo por el
                # INICIO del segmento, nunca fragmenta.
                if eliminar_ini <= ini < eliminar_fin:
                    continue  # se descarta entero
                nuevo_seg = copy.deepcopy(seg)
                if ini >= eliminar_fin:
                    nuevo_seg["target_timerange"] = {
                        "start": ini - duracion_eliminada,
                        "duration": tr["duration"],
                    }
                nuevos_segmentos.append(nuevo_seg)
                continue

            if fin <= eliminar_ini:
                # Segmento totalmente antes: no se toca, no se desplaza
                nuevo_seg = copy.deepcopy(seg)
                nuevos_segmentos.append(nuevo_seg)
                continue

            if ini >= eliminar_fin:
                # Segmento totalmente despues: se desplaza hacia atras
                nuevo_seg = copy.deepcopy(seg)
                nuevo_seg["target_timerange"] = {
                    "start": ini - duracion_eliminada,
                    "duration": tr["duration"],
                }
                nuevos_segmentos.append(nuevo_seg)
                continue

            if ini >= eliminar_ini and fin <= eliminar_fin:
                # Segmento totalmente DENTRO del tramo a eliminar: se descarta
                continue

            # Segmento que cruza un borde del tramo a eliminar (parcial)
            # - solo aplica a video/audio, donde fragmentar SI tiene sentido
            fragmentos = recortar_fuera_del_tramo(seg, eliminar_ini, eliminar_fin, 0)
            for frag in fragmentos:
                ftr = frag["target_timerange"]
                if ftr["start"] >= eliminar_fin:
                    ftr["start"] -= duracion_eliminada
                nuevos_segmentos.append(frag)

        track["segments"] = nuevos_segmentos

    data["duration"] = data["duration"] - duracion_eliminada
    return data


def aplicar_velocidad(data, factor):
    """Acelera TODO el proyecto por 'factor':
    - video/audio: cambia el material 'speed' referenciado a 'factor',
      y comprime el target_timerange a duracion/factor. source_timerange
      NO se toca (sigue tomando la misma porcion del archivo fuente).
    - texto y cualquier otro tipo: solo comprime target_timerange a
      duracion/factor (no tiene concepto de 'speed' real).
    Tambien comprime la duracion total del proyecto.
    """
    speeds_by_id = {s["id"]: s for s in data["materials"].get("speeds", [])}

    for track in data.get("tracks", []):
        for seg in track.get("segments", []):
            tr = seg.get("target_timerange")
            if tr is None:
                continue

            nueva_start = round(tr["start"] / factor)
            nueva_duration = round(tr["duration"] / factor)
            seg["target_timerange"] = {
                "start": nueva_start,
                "duration": nueva_duration,
            }

            # Cambiar el material 'speed' de este segmento, si tiene uno
            for ref in seg.get("extra_material_refs", []):
                sp = speeds_by_id.get(ref)
                if sp is not None:
                    sp["speed"] = factor

            # render_timerange (solo si tenia una duracion real, ver
            # bug ya conocido de no ensuciar el campo cuando es 0)
            rr = seg.get("render_timerange")
            if rr is not None and rr.get("duration", 0) > 0:
                rr["start"] = round(rr["start"] / factor)
                rr["duration"] = round(rr["duration"] / factor)

    data["duration"] = round(data["duration"] / factor)
    return data


def main():
    with open(RUTA_JSON_ORIGINAL, "r", encoding="utf-8") as f:
        data = json.load(f)

    duracion_inicial = data["duration"]
    print(f"Duracion inicial: {duracion_inicial/1e6:.3f}s")

    # --- Paso 1: quitar el TEXTO del titulo (no toca video/audio) ---
    for track in data.get("tracks", []):
        if track.get("type") != "text":
            continue
        track["segments"] = [
            seg for seg in track["segments"]
            if seg["id"] not in SEGMENT_IDS_TITULO_A_ELIMINAR
        ]
    print("Paso 1: titulo grafico (texto) eliminado.")

    # --- Paso 2: eliminar el tramo de km/viajes ---
    data = aplicar_eliminacion_tramo(data, ELIMINAR_INICIO_US, ELIMINAR_FIN_US)
    print(f"Paso 2: tramo {ELIMINAR_INICIO_US/1e6:.2f}s-{ELIMINAR_FIN_US/1e6:.2f}s eliminado. "
          f"Duracion ahora: {data['duration']/1e6:.3f}s")

    # --- Paso 3: acelerar todo a FACTOR_VELOCIDAD ---
    data = aplicar_velocidad(data, FACTOR_VELOCIDAD)
    print(f"Paso 3: acelerado a {FACTOR_VELOCIDAD}x. Duracion final: {data['duration']/1e6:.3f}s")

    with open(RUTA_JSON_SALIDA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print()
    print(f"Listo. Archivo nuevo escrito en: {RUTA_JSON_SALIDA}")
    print(f"Cantidad de tracks: {len(data['tracks'])}")
    for i, t in enumerate(data["tracks"]):
        print(f"  [{i}] type={t['type']} name={t['name']!r} segments={len(t['segments'])}")


if __name__ == "__main__":
    main()

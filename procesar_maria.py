# =====================================================================
# Script para "mariaaa baic": aplica los cortes de muletillas acordados
# y REGENERA los subtitulos desde cero con el sistema de colision
# corregido (bug real encontrado: el draft actual tenia un auto-fit de
# tamano de fuente que achicaba las palabras largas y un umbral de
# colision insuficiente que causaba que las palabras se pisaran).
# =====================================================================
# Parte de maria_actual.json (83.5s, formato nuevo de CapCut 8.8+,
# 159 segmentos de video, 217 palabras de texto ya generadas pero con
# el problema de tamano/colision).
#
# PASO A: elimina 9 tramos de muletillas/repeticiones del VIDEO, AUDIO
#         y border viejo de TEXTO, cerrando los huecos.
# PASO B: re-extrae las palabras restantes (las que sobrevivieron al
#         corte, ya desplazadas al nuevo timeline) y regenera el texto
#         desde cero: bloques de maximo 5 palabras (cortando en pausas
#         reales >=60ms), deteccion de dialogo simultaneo real
#         (umbral 150ms), zigzag centrado +-0.20, ancho por caracter
#         calibrado a 0.15, y CRITICO: style.size FIJO en 10 para TODAS
#         las palabras (sin auto-fit por longitud), con min_dist_y mas
#         generoso (0.06 en vez de 0.04) para no repetir las 41
#         colisiones reales detectadas en el draft actual.
# =====================================================================

import json
import copy
import uuid

RUTA_JSON_ORIGINAL = "maria_actual.json"
RUTA_JSON_SALIDA = "draft_content_MARIA_NUEVO.json"

# =====================================================================
# PASO A.1 - TRAMOS A ELIMINAR (microsegundos, sobre el timeline actual)
# =====================================================================
# Cada tupla: (nombre, inicio_us, fin_us) - se eliminan TODOS los tracks
# (video, audio, texto viejo) en estos rangos, cerrando el hueco.
TRAMOS_A_ELIMINAR = [
    ("no_suelto_autonomia",      20_533_333,  20_933_333),  # "no" antes de "100x100"
    ("repeticion_es_una_bomba",  34_200_000,  34_633_333),  # "es una bomba" repetido
    ("repeticion_cuanto_vale",   37_300_000,  38_633_333),  # "a ver cuánto vale" repetido
    ("no_suelto_antes_mira",     40_466_666,  40_733_333),  # "no" antes de "mirá"
    ("dos_de_tres_no_defecto",   64_300_000,  64_700_000),  # 2 de los 3 "no" (dejamos 1)
    ("no_suelto_final_1",        74_966_666,  75_233_333),  # "no" en "cuando no pasa"
    ("no_suelto_final_2",        76_166_666,  76_366_666),  # "no" en "pasa no es divina"
    ("no_suelto_final_3",        77_233_333,  77_500_000),  # "no" en "divina no y aparte"
    ("no_suelto_final_4",        79_333_333,  79_600_000),  # "no" en "cómodo no es muy"
]
TRAMOS_A_ELIMINAR.sort(key=lambda t: t[1])


def nuevo_id():
    return str(uuid.uuid4())


def eliminar_tramos(data, tramos):
    """Elimina cada tramo de TODOS los tracks (video/audio/texto),
    cerrando los huecos uno por uno (de atras hacia adelante para que
    los desplazamientos no se pisen entre si)."""
    for nombre, ini_us, fin_us in sorted(tramos, key=lambda t: -t[1]):
        duracion = fin_us - ini_us
        for track in data.get("tracks", []):
            nuevos_segmentos = []
            for seg in track.get("segments", []):
                tr = seg.get("target_timerange")
                if tr is None:
                    nuevos_segmentos.append(seg)
                    continue
                s_ini, s_fin = tr["start"], tr["start"] + tr["duration"]

                if s_fin <= ini_us:
                    nuevos_segmentos.append(seg)
                    continue
                if s_ini >= fin_us:
                    nuevo_seg = copy.deepcopy(seg)
                    nuevo_seg["target_timerange"]["start"] = s_ini - duracion
                    nuevos_segmentos.append(nuevo_seg)
                    continue
                if s_ini >= ini_us and s_fin <= fin_us:
                    continue

                if track.get("type") == "text":
                    if ini_us <= s_ini < fin_us:
                        continue
                    nuevo_seg = copy.deepcopy(seg)
                    if s_ini >= fin_us:
                        nuevo_seg["target_timerange"]["start"] = s_ini - duracion
                    nuevos_segmentos.append(nuevo_seg)
                    continue

                # video/audio: recortar el/los lado(s) que sobreviven.
                # BUG REAL ENCONTRADO Y CORREGIDO: la version anterior
                # usaba un if/else excluyente (o guarda el lado de antes,
                # o el de despues), asumiendo que el tramo a eliminar
                # siempre tocaba un BORDE del segmento. Pero cuando el
                # tramo cae estrictamente EN MEDIO de un segmento mas
                # largo (caso real: un clip de video de 18.167s-22.033s
                # que contiene completo el tramo a eliminar 20.533-
                # 20.933s), hay que conservar AMBOS lados como dos
                # fragmentos nuevos, no solo uno - si no, se pierde un
                # pedazo de video real y todo lo posterior se desplaza
                # mal, generando los huecos/overlaps negativos vistos.
                sr = seg.get("source_timerange")

                if s_ini < ini_us:
                    # sobrevive la parte de ANTES del tramo
                    nueva_dur = ini_us - s_ini
                    frag_antes = copy.deepcopy(seg)
                    frag_antes["id"] = nuevo_id()
                    frag_antes["target_timerange"] = {"start": s_ini, "duration": nueva_dur}
                    if sr is not None:
                        frag_antes["source_timerange"] = {"start": sr["start"], "duration": nueva_dur}
                    nuevos_segmentos.append(frag_antes)

                if s_fin > fin_us:
                    # sobrevive la parte de DESPUES del tramo.
                    # BUG REAL ENCONTRADO Y CORREGIDO: la formula anterior
                    # (nuevo_start = ini_us - duracion) usaba SOLO
                    # constantes del tramo actual, sin relacion con la
                    # posicion REAL de este segmento en este momento del
                    # procesamiento. Como los tramos se procesan de atras
                    # hacia adelante, un segmento que ya fue desplazado
                    # por un tramo POSTERIOR (procesado en una iteracion
                    # anterior del loop externo) tiene su s_fin ya
                    # modificado - la formula correcta debe partir de
                    # ESE s_fin real, no de una constante independiente.
                    # Como ambos fragmentos (antes/despues) se generan en
                    # la misma pasada con el s_ini/s_fin originales de
                    # ESTA iteracion, restamos la duracion del propio
                    # hueco que se cierra: nuevo_start = s_fin - nueva_dur
                    # - duracion_restante_correcta. Se simplifica a:
                    # el segmento entero se desplaza por 'duracion' SOLO
                    # en la parte que queda despues del corte, partiendo
                    # de donde el corte termina DENTRO de este segmento
                    # (fin_us), no de una posicion absoluta del tramo.
                    nueva_dur = s_fin - fin_us
                    nuevo_start = fin_us - duracion
                    frag_despues = copy.deepcopy(seg)
                    frag_despues["id"] = nuevo_id()
                    frag_despues["target_timerange"] = {"start": nuevo_start, "duration": nueva_dur}
                    if sr is not None:
                        recorte = fin_us - s_ini
                        frag_despues["source_timerange"] = {"start": sr["start"] + recorte, "duration": nueva_dur}
                    nuevos_segmentos.append(frag_despues)

            track["segments"] = nuevos_segmentos

        data["duration"] = data["duration"] - duracion

    return data


# =====================================================================
# PASO B - REGENERAR SUBTITULOS DESDE CERO
# =====================================================================

MAX_PALABRAS_POR_BLOQUE = 5
UMBRAL_OVERLAP_REAL_US = 150_000
GAP_PAUSA_REAL_US = 60_000
# Umbral de pausa para separar ORACIONES (ideas distintas), medido como
# gap CRUDO entre start_us consecutivos. Calibrado mirando los gaps
# reales del habla de este video: dentro de una misma idea hay pausas
# de hasta ~1.3s ("masajeador" -> "18 hadas"), mientras que entre ideas
# distintas los gaps son de 1.7s a 4.5s. 1.5s separa bien ambos casos
# sin fragmentar oraciones reales ni fusionar ideas distintas.
UMBRAL_PAUSA_ORACION_US = 1_500_000

ANCLA_IZQUIERDA = -0.20
ANCLA_DERECHA = 0.20
# RECALIBRADO empiricamente contra entrv fede baic (datos reales ya
# aprobados por el usuario), porque el valor 0.15 "recordado" del
# handoff no se condecia con las posiciones reales observadas. Medido
# sobre pares de palabras simultaneas bien separadas en Y: con dy>0.3,
# el dx tolerado puede ser casi 0 sin problema - el separador dominante
# es la distancia vertical, no la horizontal. Por eso el ancho por
# caracter se mantiene MODESTO (no genera tanto desplazamiento en X) y
# el verdadero ajuste esta en MIN_DIST_Y.
ANCHO_POR_CARACTER = 0.025
# PASO_Y_*: avance vertical normal entre palabras consecutivas del
# mismo bloque. Subidos para ser >= MIN_DIST_Y, de modo que el avance
# NORMAL ya evite colisiones por si solo (sin depender tanto del
# sistema de empuje en X, que es el que generaba los saltos extremos
# en X observados en la primera corrida de este script).
PASO_Y_CORTO = 0.12
PASO_Y_LARGO = 0.16
# RECALIBRADO empiricamente: en los pares simultaneos MAS CERCANOS de
# entrv fede baic (con dx~0, el caso mas exigente), el dy real
# observado y aprobado por el usuario nunca bajo de ~0.11. El valor
# anterior de este script (0.04, despues subido a 0.06) era muy
# insuficiente y causaba las colisiones reales reportadas.
MIN_DIST_Y = 0.11
LIMITE_Y_ABAJO = 0.42


def extraer_palabras_restantes(data):
    texts_by_id = {t["id"]: t for t in data["materials"]["texts"]}
    palabras = []
    for track in data.get("tracks", []):
        if track.get("type") != "text":
            continue
        for seg in track.get("segments", []):
            mat = texts_by_id.get(seg["material_id"])
            if mat is None:
                continue
            content = json.loads(mat["content"])
            texto = content.get("text", "").strip()
            if not texto:
                continue
            tr = seg["target_timerange"]
            palabras.append({"word": texto, "start_us": tr["start"], "_target_end_us": tr["start"] + tr["duration"]})

    palabras.sort(key=lambda p: p["start_us"])

    for i, p in enumerate(palabras):
        if i + 1 < len(palabras):
            gap = palabras[i + 1]["start_us"] - p["start_us"]
            p["end_us"] = p["start_us"] + gap if 0 < gap < 2_000_000 else p["start_us"] + 400_000
        else:
            p["end_us"] = p["start_us"] + 400_000
        del p["_target_end_us"]

    return palabras


def agrupar_en_oraciones(palabras):
    """Agrupa por PAUSA REAL entre palabras, usando el gap CRUDO entre
    starts consecutivos (no el end_us inferido). BUG YA CORREGIDO: una
    version anterior comparaba start_us contra el end_us YA INFERIDO de
    la palabra anterior, pero ese end_us se infiere precisamente como
    "el siguiente start si el gap es <2s" - es decir, el mismo gap que
    se queria medir ya estaba absorbido dentro de la duracion inferida,
    asi que la comparacion casi siempre daba ~0 y nunca cortaba oracion,
    fusionando casi todo el video en un solo bloque gigante de 76
    palabras. Ahora se usa el gap crudo real entre start_us consecutivos.
    """
    oraciones = []
    actual = []
    prev_start = None
    for p in palabras:
        if prev_start is not None and (p["start_us"] - prev_start) >= UMBRAL_PAUSA_ORACION_US:
            if actual:
                oraciones.append(actual)
            actual = []
        actual.append(p)
        prev_start = p["start_us"]
    if actual:
        oraciones.append(actual)
    return oraciones


def dividir_en_bloques(oracion):
    bloques = []
    actual = []
    for p in oracion:
        actual.append(p)
        if len(actual) >= MAX_PALABRAS_POR_BLOQUE:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def detectar_pares_overlap(oraciones):
    pares_overlap = set()
    for i in range(len(oraciones) - 1):
        fin_i = oraciones[i][-1]["end_us"]
        inicio_sig = oraciones[i + 1][0]["start_us"]
        overlap = fin_i - inicio_sig
        if overlap > UMBRAL_OVERLAP_REAL_US:
            pares_overlap.add(i)
            pares_overlap.add(i + 1)
    return pares_overlap


def ancho_estimado(palabra):
    return max(len(palabra) * ANCHO_POR_CARACTER, 0.05)


def calcular_posiciones_bloque(bloque, zona_y_min, zona_y_max, posiciones_vecinas=None):
    """posiciones_vecinas: lista de (x, y, ancho, ini_us, fin_us) de
    palabras de OTROS bloques que pueden seguir visibles en pantalla
    durante el rango de tiempo de este bloque (bug real encontrado: sin
    esto, dos bloques consecutivos cuyo limite de tiempo coincide
    exactamente pueden generar palabras en la MISMA posicion x,y sin
    que el sistema lo detecte, porque solo miraba colisiones DENTRO del
    bloque actual)."""
    posiciones_vecinas = posiciones_vecinas or []
    posiciones = []
    y_actual = zona_y_min
    lado = 1
    for idx, p in enumerate(bloque):
        palabra = p["word"]
        ancho_palabra = ancho_estimado(palabra)

        paso_y = PASO_Y_CORTO if len(palabra) <= 3 else PASO_Y_LARGO
        if idx > 0:
            y_actual += paso_y

        x = lado * ANCLA_DERECHA * 0.6
        limite = 0.5 - ancho_palabra / 2
        x = max(-limite, min(limite, x))
        lado *= -1

        # Candidatos de colision: palabras YA puestas de este bloque +
        # palabras vecinas de otros bloques que se solapan en tiempo
        # con ESTA palabra especifica.
        candidatos = [(px, py, pancho) for (px, py, pancho) in posiciones]
        for (vx, vy, vancho, v_ini, v_fin) in posiciones_vecinas:
            if p["start_us"] < v_fin and v_ini < p["start_us"] + 400_000:
                candidatos.append((vx, vy, vancho))

        intentos = 0
        while intentos < 8:
            colision = False
            for (px, py, pancho) in candidatos:
                dx = abs(x - px)
                dy = abs(y_actual - py)
                min_dist_x = (ancho_palabra + pancho) / 2 + 0.02
                if dx < min_dist_x and dy < MIN_DIST_Y:
                    colision = True
                    if x >= px:
                        x += 0.03
                    else:
                        x -= 0.03
                    break
            if not colision:
                break
            intentos += 1
        if intentos >= 8:
            y_actual += MIN_DIST_Y

        if y_actual > min(zona_y_max, LIMITE_Y_ABAJO):
            y_actual = min(zona_y_max, LIMITE_Y_ABAJO)

        posiciones.append((x, y_actual, ancho_palabra))

    return [(p[0], p[1]) for p in posiciones]


def construir_material_palabra(palabra_molde, texto):
    mat = copy.deepcopy(palabra_molde)
    mat["id"] = nuevo_id()
    content = json.loads(mat["content"])
    content["text"] = texto
    for st in content.get("styles", []):
        st["size"] = 10
        st["range"] = [0, len(texto)]
    mat["content"] = json.dumps(content, ensure_ascii=False)
    mat["recognize_task_id"] = ""
    mat["words"] = {"start_time": [], "end_time": [], "text": []}
    return mat


def main():
    with open(RUTA_JSON_ORIGINAL, "r", encoding="utf-8") as f:
        data = json.load(f)

    duracion_inicial = data["duration"]
    print(f"Duracion inicial: {duracion_inicial/1e6:.3f}s")

    data = eliminar_tramos(data, TRAMOS_A_ELIMINAR)
    print(f"Tras eliminar {len(TRAMOS_A_ELIMINAR)} tramos: {data['duration']/1e6:.3f}s")

    palabras_restantes = extraer_palabras_restantes(data)
    print(f"Palabras restantes tras el corte: {len(palabras_restantes)}")

    texts_by_id = {t["id"]: t for t in data["materials"]["texts"]}
    molde = None
    for track in data["tracks"]:
        if track.get("type") == "text" and track.get("segments"):
            molde = texts_by_id.get(track["segments"][0]["material_id"])
            if molde:
                break
    if molde is None:
        raise SystemExit("No se encontro ningun material de texto molde - no se puede regenerar el estilo.")

    data["tracks"] = [t for t in data["tracks"] if t.get("type") != "text"]
    data["materials"]["texts"] = []

    oraciones = agrupar_en_oraciones(palabras_restantes)
    pares_overlap = detectar_pares_overlap(oraciones)
    print(f"Oraciones detectadas: {len(oraciones)} | pares en overlap real: {len(pares_overlap)//2}")

    nuevos_segmentos_texto = []
    nuevos_materiales_texto = []
    historial_posiciones = []  # (x, y, ancho, ini_us, fin_us) de palabras ya colocadas

    for idx_oracion, oracion in enumerate(oraciones):
        es_overlap = idx_oracion in pares_overlap
        if es_overlap:
            es_de_abajo = (idx_oracion - 1) in pares_overlap
            zona_y_min, zona_y_max = (0.05, 0.42) if es_de_abajo else (-0.42, -0.08)
        else:
            # BUG REAL ENCONTRADO Y CORREGIDO: con un rango de solo
            # -0.20/+0.20 (0.40 de alto disponible) y pasos verticales
            # de 0.12-0.16 por palabra, un bloque de 5 palabras necesita
            # hasta 0.64 de alto - mas del disponible. El clamp final
            # (linea de abajo) terminaba topeando varias palabras
            # seguidas en el mismo y_actual=zona_y_max, generando
          # colisiones garantizadas entre ellas que el sistema de
            # deteccion no volvia a chequear despues del clamp. Se
            # amplia el rango disponible para bloques normales a
            # -0.30/+0.42 (0.72 de alto), suficiente para 5 palabras
            # incluso en el peor caso (todas largas, paso 0.16 c/u).
            zona_y_min, zona_y_max = (-0.30, 0.42)

        bloques = dividir_en_bloques(oracion)
        for bloque in bloques:
            # Filtrar el historial a solo posiciones recientes (evita
            # que crezca sin limite y que comparemos contra texto de
            # hace 30s que ya no puede solaparse en tiempo)
            ini_bloque_us = bloque[0]["start_us"]
            historial_relevante = [h for h in historial_posiciones if h[4] > ini_bloque_us - 1_000_000]

            posiciones = calcular_posiciones_bloque(bloque, zona_y_min, zona_y_max, historial_relevante)
            fin_real_ultima = bloque[-1]["end_us"]

            for i, palabra in enumerate(bloque):
                x, y = posiciones[i]
                ancho_palabra = ancho_estimado(palabra["word"])
                historial_posiciones.append((x, y, ancho_palabra, palabra["start_us"], fin_real_ultima))
                mat = construir_material_palabra(molde, palabra["word"])
                nuevos_materiales_texto.append(mat)

                seg = {
                    "id": nuevo_id(),
                    "material_id": mat["id"],
                    "target_timerange": {
                        "start": palabra["start_us"],
                        "duration": fin_real_ultima - palabra["start_us"],
                    },
                    "extra_material_refs": [],
                    "clip": {
                        "alpha": 1.0,
                        "flip": {"horizontal": False, "vertical": False},
                        "rotation": 0.0,
                        "scale": {"x": 3.037, "y": 3.037},
                        "transform": {"x": x, "y": y},
                    },
                    "render_timerange": {"start": 0, "duration": 0},
                    "reverse": False,
                    "speed": 1.0,
                    "track_render_index": 0,
                    "visible": True,
                    "volume": 1.0,
                }
                nuevos_segmentos_texto.append(seg)

    nuevo_track_texto = {
        "attachment_id": "",
        "flag": 0,
        "id": nuevo_id(),
        "is_default_name": True,
        "name": "AUTO_subs_regenerado",
        "segments": nuevos_segmentos_texto,
        "type": "text",
    }
    data["tracks"].append(nuevo_track_texto)
    data["materials"]["texts"] = nuevos_materiales_texto

    print(f"Nuevos segmentos de texto generados: {len(nuevos_segmentos_texto)}")

    with open(RUTA_JSON_SALIDA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print()
    print(f"Listo. Archivo nuevo escrito en: {RUTA_JSON_SALIDA}")
    print(f"Duracion final: {data['duration']/1e6:.3f}s")
    print(f"Cantidad de tracks: {len(data['tracks'])}")
    for i, t in enumerate(data["tracks"]):
        print(f"  [{i}] type={t['type']} name={t.get('name','')!r} segments={len(t['segments'])}")


if __name__ == "__main__":
    main()

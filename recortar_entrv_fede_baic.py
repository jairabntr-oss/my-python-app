# =====================================================================
# Script para recortar y reordenar "entrv fede baic" segun el nuevo guion
# acordado con la jefa (hook al inicio, sin presentacion, cartel VIP).
# =====================================================================
# QUE HACE:
#   1. Lee el draft_content.json ORIGINAL (sin tocar el archivo real de
#      CapCut todavia - trabaja sobre una copia).
#   2. Define los BLOQUES finales (rangos de tiempo del video ORIGINAL
#      que se mantienen, en el orden nuevo).
#   3. Para CADA track (video, audio, texto) recorre sus segmentos y:
#      - Si un segmento cae COMPLETO dentro de un bloque que se mantiene,
#        lo conserva, recalculando su nueva posicion en el timeline final
#        segun el offset acumulado de los bloques anteriores.
#      - Si un segmento cae COMPLETO fuera de todos los bloques, se
#        descarta.
#      - Si un segmento CRUZA el limite de un bloque (entra una parte,
#        sale la otra), se recorta su target_timerange Y su
#        source_timerange proporcionalmente, para no mostrar contenido
#        que no corresponde.
#   4. El HOOK (bloque "C", fragmento 26.80s-29.87s) se inserta DOS
#      veces: una al principio (clonando los materiales para no romper
#      referencias compartidas) y otra en su lugar original dentro del
#      bloque grande de la entrevista.
#   5. Agrega un track de texto nuevo con el cartel fijo "Fede Mestre
#      Cliente VIP Baic Long", abajo a la izquierda, visible durante
#      TODO el video final.
#   6. Ajusta la duracion total del draft.
#   7. Guarda el resultado en un archivo NUEVO (no pisa el original),
#      para que lo revises antes de copiarlo al draft real de CapCut.
#
# IMPORTANTE - LEER ANTES DE CORRER:
#   - Este script NO escribe directo sobre tu draft de CapCut. Genera un
#     archivo nuevo (draft_content_NUEVO.json) que despues hay que copiar
#     a mano (o con el script auxiliar que se imprime al final).
#   - Los clicks de audio (track con material "click_subtitulo") quedan
#     RECORTADOS junto con sus bloques, pero al juntar bloques que antes
#     estaban separados en el tiempo pueden quedar clicks muy pegados o
#     espaciados de forma rara. Si despues de revisar el video los clicks
#     no te convencen, lo mas facil es borrar ese track en CapCut a mano
#     y re-generarlo con agregar_clicks_baic.py sobre el draft YA cortado.
#   - CapCut tiene que estar CERRADO mientras se corre este script y
#     mientras se reemplaza el draft_content.json.
# =====================================================================

import json
import copy
import uuid

# =====================================================================
# PASO A - CONFIGURACION: rutas de entrada/salida
# =====================================================================

RUTA_JSON_ORIGINAL = "draft_original.json"  # copia del draft_content.json real
RUTA_JSON_SALIDA = "draft_content_NUEVO.json"

# =====================================================================
# PASO B - BLOQUES FINALES (acordados con la jefa)
# =====================================================================
# Cada bloque es (nombre, inicio_seg, fin_seg) en el tiempo del video
# ORIGINAL. Van en el ORDEN en que deben aparecer en el video final.
#
# El primer bloque ("HOOK") es una REPETICION de un fragmento que
# tambien aparece mas adelante (bloque "C_completo") en su lugar
# original. Por eso decimos duplicar=True: el script va a clonar los
# materiales de ese fragmento para insertarlos sueltos al principio,
# sin tocar la aparicion original de mas adelante.

BLOQUES = [
    # nombre                  inicio    fin       duplicar (clona en vez de mover)
    ("TITULO",                0.00,     0.30,     False),
    ("HOOK_inicio",           26.80,    29.87,    True),   # clon del fragmento que reaparece en C
    ("B_vehiculo_BJ30",       2.13,     7.07,     False),
    ("C_completo",            7.47,    29.87,     False),  # incluye el hook "real", en su lugar
    ("D_hace_cuanto",         30.53,    35.47,    False),
    ("E_kilometros",          35.80,    38.80,    False),
    ("F_viajes",              39.50,    42.57,    False),
    ("G_le_metimos",          43.30,    47.33,    False),
    ("H_hija_espacio",        47.87,    57.90,    False),
    ("I_interior_tecnologia", 58.23,    66.40,    False),
    ("J_recortado_manejarla", 74.57,    76.57,    False),
    ("K_recortado_traemela",  79.97,    90.13,    False),
]

# Convertir a microsegundos para trabajar en las mismas unidades que el JSON
BLOQUES_US = [
    (nombre, int(round(ini * 1_000_000)), int(round(fin * 1_000_000)), dup)
    for nombre, ini, fin, dup in BLOQUES
]

# =====================================================================
# PASO B.1 - ELEMENTOS A EXCLUIR POR COMPLETO (no recortar, descartar)
# =====================================================================
# Se detecto un text_template residual ("Trendy EN M5 my plan today", un
# efecto/sticker comprado de CapCut) que dura casi todo el video
# (1.3s-88.7s) pero el usuario confirmo que NO se ve nada en pantalla en
# esa zona - es basura que quedo de alguna prueba. Si intentaramos
# recortarlo bloque por bloque como a cualquier otro segmento, al durar
# casi todo el video se fragmentaria en un pedacito por cada uno de los
# 12 bloques finales, generando ruido. Por eso se excluye DIRECTO por
# material_id, antes de aplicar la logica de bloques.
MATERIAL_IDS_EXCLUIR = {
    "57FCFE94-0EE6-443f-9660-77094B30E73B",  # text_template residual sin uso visible
}

# En los bloques marcados como duplicar=True (el HOOK del principio),
# el usuario decidio que SOLO se escuche la voz de Fede (que viaja
# embebida en el track de VIDEO, el .mov), sin musica de fondo ni
# efectos de sonido. Por eso, en esos bloques, se descartan por completo
# los segmentos de los tracks de AUDIO (musica, clicks, efectos como la
# "moneda"), y se conservan solo los de video (con su voz) y texto
# (subtitulos). Esto reemplaza un filtro anterior por "fraccion minima
# conservada" que daba este mismo resultado pero de forma fragil/casual
# (descartaba la musica porque su clip original era larguisimo y la
# fraccion conservada quedaba debajo del umbral) - ahora es una regla
# explicita y predecible.
DESCARTAR_AUDIO_EN_DUPLICADOS = True

# =====================================================================
# PASO C - CARTEL FIJO NUEVO
# =====================================================================

TEXTO_CARTEL = "Fede Mestre\nCliente VIP Baic Long"
CARTEL_TRANSFORM_X = -0.62
CARTEL_TRANSFORM_Y = 0.78
CARTEL_SCALE = 2.0  # mas chico que el titulo (4.18) pero legible, similar al estilo de subtitulos

NOMBRE_TRACK_CARTEL = "Cartel Fede VIP"

# =====================================================================
# PASO D - FUNCIONES DE RECORTE
# =====================================================================

def nuevo_id():
    """Genera un material_id / segment id nuevo con formato similar al de CapCut."""
    return str(uuid.uuid4()).upper()


def segmento_offset_y_recorte(seg, bloque_inicio_us, bloque_fin_us, offset_destino_us):
    """Dado un segmento (con target_timerange / source_timerange en us) y un
    bloque [bloque_inicio_us, bloque_fin_us) del timeline ORIGINAL que se
    mantiene, calcula el segmento resultante reubicado en el timeline NUEVO
    a partir de offset_destino_us.

    Devuelve None si el segmento no se solapa en absoluto con el bloque.
    Si el segmento cruza el borde del bloque, lo recorta proporcionalmente
    (tanto target como source), para no incluir contenido que quedo fuera
    del corte.
    """
    tr = seg.get("target_timerange")
    if tr is None:
        # Segmentos sin target_timerange (no deberia pasar en video/audio/texto,
        # pero por si acaso los dejamos pasar sin tocar)
        return copy.deepcopy(seg)

    seg_ini = tr["start"]
    seg_fin = tr["start"] + tr["duration"]

    # Sin solapamiento => se descarta
    nuevo_ini = max(seg_ini, bloque_inicio_us)
    nuevo_fin = min(seg_fin, bloque_fin_us)
    if nuevo_fin <= nuevo_ini:
        return None

    recorte_inicio = nuevo_ini - seg_ini  # cuanto se recorta del principio
    recorte_fin = seg_fin - nuevo_fin     # cuanto se recorta del final
    nueva_duracion = nuevo_fin - nuevo_ini

    nuevo_seg = copy.deepcopy(seg)

    # Nueva posicion en el timeline FINAL
    nuevo_seg["target_timerange"] = {
        "start": offset_destino_us + (nuevo_ini - bloque_inicio_us),
        "duration": nueva_duracion,
    }

    # Si el material tiene source_timerange (video/audio), recortarlo en la
    # misma proporcion para no reproducir contenido fuente que quedo afuera.
    sr = seg.get("source_timerange")
    if sr is not None:
        nuevo_seg["source_timerange"] = {
            "start": sr["start"] + recorte_inicio,
            "duration": sr["duration"] - recorte_inicio - recorte_fin,
        }

    # render_timerange: en los datos reales de CapCut, los segmentos de
    # video/audio normales tienen render_timerange = {"start": 0,
    # "duration": 0} como valor "sin usar/no aplica" (confirmado: TODOS
    # los segmentos de video/audio del draft original lo tienen en 0).
    # BUG YA CORREGIDO: una version anterior de este script reescribia
    # ese campo con la nueva duracion recortada incluso cuando el
    # original era 0, "ensuciando" un campo que CapCut espera en 0 para
    # esos segmentos - esto coincidio con que CapCut descartara en
    # silencio un segmento real al reabrir el draft (mismo patron de bug
    # ya documentado: un campo con un valor que CapCut no espera hace que
    # descarte el segmento sin avisar). Ahora SOLO se recalcula
    # render_timerange si el original ya tenia una duracion real (>0),
    # que es el caso de ciertos clips de texto con animacion.
    rr = seg.get("render_timerange")
    if rr is not None and rr.get("duration", 0) > 0:
        nuevo_seg["render_timerange"] = {
            "start": rr.get("start", nuevo_seg["target_timerange"]["start"]),
            "duration": nueva_duracion,
        }

    return nuevo_seg


def procesar_track(track, materials_by_id_dict, origen_lista_by_id, clonar_materiales=False):
    """Recorre los segmentos de un track y devuelve la lista de nuevos
    segmentos (recortados/reubicados) segun BLOQUES_US, en el ORDEN de
    los bloques (no en el orden original).

    Si clonar_materiales=True (usado para los bloques marcados con
    duplicar=True), cada segmento que sobreviva se clona con un id de
    segmento Y de material nuevos, y el material correspondiente se
    duplica en materials_by_id_dict (y se registra en origen_lista_by_id
    con el mismo tipo que el material original), para que la copia del
    hook al principio no comparta referencia con la aparicion original.
    """
    es_track_audio = track.get("type") == "audio"
    nuevos_segmentos = []
    offset_acumulado = 0

    for nombre_bloque, ini_us, fin_us, duplicar in BLOQUES_US:
        for seg in track.get("segments", []):
            if seg.get("material_id") in MATERIAL_IDS_EXCLUIR:
                continue

            duracion_original = None
            tr_orig = seg.get("target_timerange")
            if tr_orig is not None:
                duracion_original = tr_orig["duration"]

            resultado = segmento_offset_y_recorte(seg, ini_us, fin_us, offset_acumulado)
            if resultado is None:
                continue

            # En bloques duplicados (el HOOK del principio), el usuario
            # quiere SOLO la voz (embebida en el video), sin musica ni
            # efectos de fondo: por eso se descartan por completo los
            # segmentos de tracks de AUDIO en esos bloques.
            if duplicar and es_track_audio and DESCARTAR_AUDIO_EN_DUPLICADOS:
                continue

            # BUG REAL ENCONTRADO Y CORREGIDO: un mismo segmento del
            # ORIGINAL puede solaparse con DOS bloques finales distintos
            # cuando el corte entre bloques cae justo en medio de ese
            # segmento (caso real: un clip de video de 4.4s-9.4s que
            # cruza el limite entre el bloque B, que termina en 7.07s, y
            # el bloque C, que empieza en 7.47s). Eso genera DOS
            # fragmentos distintos a partir del mismo segmento original.
            # Antes, el nuevo "id" de segmento SOLO se regeneraba cuando
            # duplicar=True, así que esos dos fragmentos quedaban con el
            # MISMO id de segmento (clonado tal cual del original) dentro
            # del mismo track. CapCut no tolera ids de segmento
            # duplicados en un track y descarta uno de los dos en
            # silencio - exactamente el sintoma real visto (un fragmento
            # de video desaparecia y todo lo posterior se desincronizaba
            # una posicion). Por eso TODO segmento resultante de un corte
            # recibe SIEMPRE un id nuevo, sin condicionarlo a "duplicar".
            resultado["id"] = nuevo_id()

            if duplicar:
                # Ademas del id de segmento (ya regenerado arriba),
                # clonar tambien el MATERIAL (audio/video/texto real) y
                # registrar el clon en los diccionarios, para que la
                # copia del hook al principio no comparta referencia de
                # material con la aparicion original mas adelante.
                mat_id_original = resultado.get("material_id")
                if mat_id_original and mat_id_original in materials_by_id_dict:
                    mat_original = materials_by_id_dict[mat_id_original]
                    mat_clonado = copy.deepcopy(mat_original)
                    nuevo_mat_id = nuevo_id()
                    mat_clonado["id"] = nuevo_mat_id
                    materials_by_id_dict[nuevo_mat_id] = mat_clonado
                    origen_lista_by_id[nuevo_mat_id] = origen_lista_by_id.get(mat_id_original, "texts")
                    resultado["material_id"] = nuevo_mat_id
                elif mat_id_original:
                    print(f"AVISO: segmento clonado referenciaba material_id {mat_id_original} "
                          f"que no esta indexado; el clon queda apuntando al mismo id original "
                          f"(podria no clonarse del todo bien, revisar a mano este caso).")

            nuevos_segmentos.append(resultado)

        # Avanzar el offset de destino por la duracion REAL de este bloque
        offset_acumulado += (fin_us - ini_us)

    nuevo_track = copy.deepcopy(track)
    nuevo_track["segments"] = nuevos_segmentos
    return nuevo_track


# =====================================================================
# PASO E - CONSTRUCCION DEL MATERIAL DE TEXTO PARA EL CARTEL FIJO
# =====================================================================

def construir_material_cartel(material_molde):
    """A partir de un material de texto karaoke real (el molde de estilo
    ya validado: Poppins-Bold, size 10, sombra calibrada), construye un
    material NUEVO para el cartel fijo, cambiando solo el texto.
    """
    mat = copy.deepcopy(material_molde)
    nuevo_mat_id = nuevo_id()
    mat["id"] = nuevo_mat_id
    mat["name"] = ""
    # El cartel es texto manual nuestro, no viene de reconocimiento de voz:
    # sacamos recognize_task_id para que no lo confunda ningun script de
    # limpieza/clasificacion futuro con auto-caption real.
    mat["recognize_task_id"] = ""
    mat["recognize_text"] = ""
    mat["words"] = {"start_time": [], "end_time": [], "text": []}
    mat["current_words"] = {"start_time": [], "end_time": [], "text": []}

    content_obj = json.loads(mat["content"])
    content_obj["text"] = TEXTO_CARTEL
    # un solo style que cubra todo el rango del texto nuevo
    estilo_base = content_obj["styles"][0]
    estilo_base["range"] = [0, len(TEXTO_CARTEL)]
    content_obj["styles"] = [estilo_base]
    mat["content"] = json.dumps(content_obj, ensure_ascii=False)
    mat["base_content"] = mat["content"]

    return mat, nuevo_mat_id


def construir_track_cartel(material_id_cartel, duracion_total_us, segmento_molde):
    """Crea el track de texto nuevo para el cartel, con un solo segmento
    que dura TODO el video final.

    IMPORTANTE: en vez de armar el segmento a mano (que se queda corto en
    campos obligatorios que CapCut espera - render_index, source,
    enable_video_mask, responsive_layout, etc., y los descarta en
    silencio al abrir el draft, igual que el bug ya documentado con el
    material_id de audio en agregar_clicks_baic.py), CLONAMOS un segmento
    de texto real del draft y solo le pisamos los campos que nos importan
    (id, material_id, timerange, clip/transform/scale). Esto garantiza
    que ningun campo obligatorio quede faltante.
    """
    seg = copy.deepcopy(segmento_molde)
    seg["id"] = nuevo_id()
    seg["material_id"] = material_id_cartel
    seg["target_timerange"] = {"start": 0, "duration": duracion_total_us}
    seg["source_timerange"] = None
    seg["render_timerange"] = {"start": 0, "duration": 0}
    seg["clip"] = {
        "scale": {"x": CARTEL_SCALE, "y": CARTEL_SCALE},
        "rotation": 0.0,
        "transform": {"x": CARTEL_TRANSFORM_X, "y": CARTEL_TRANSFORM_Y},
        "flip": {"vertical": False, "horizontal": False},
        "alpha": 1.0,
    }
    seg["uniform_scale"] = {"on": True, "value": CARTEL_SCALE}
    # El cartel no depende de ningun extra_material_ref del original (ese
    # ref suele apuntar a una animacion/efecto particular de la palabra
    # clonada, que no necesariamente aplica aca) - lo vaciamos para no
    # heredar una animacion de entrada/salida que no calibramos.
    seg["extra_material_refs"] = []

    return {
        "type": "text",
        "name": NOMBRE_TRACK_CARTEL,
        "attribute": 0,
        "flag": 0,
        "is_default_name": False,
        "segments": [seg],
    }


# =====================================================================
# PASO F - PROGRAMA PRINCIPAL
# =====================================================================

def main():
    with open(RUTA_JSON_ORIGINAL, "r", encoding="utf-8") as f:
        data = json.load(f)

    materials = data.get("materials", {})

    # Indice de materiales por id, recorriendo TODAS las listas de
    # materials (no solo videos/audios/texts). Esto es importante porque
    # un segmento de un track de texto puede referenciar un material que
    # en realidad vive en otra lista (ej. "text_templates", "stickers",
    # "effects") - como paso con el text_template residual detectado en
    # este draft. Si solo indexamos texts/videos/audios y un segmento
    # referencia algo de otra lista, lo tratamos como excluido en vez de
    # romper con un material_id inexistente.
    TIPOS_MATERIAL_RELEVANTES = (
        "videos", "audios", "texts", "text_templates", "stickers",
        "effects", "images",
    )
    materiales_by_id = {}
    origen_lista_by_id = {}
    for tipo in TIPOS_MATERIAL_RELEVANTES:
        for m in materials.get(tipo, []):
            if isinstance(m, dict) and "id" in m:
                materiales_by_id[m["id"]] = m
                origen_lista_by_id[m["id"]] = tipo

    duracion_total_us = sum(fin - ini for _, ini, fin, _ in BLOQUES_US)
    print(f"Duracion total del video final: {duracion_total_us/1_000_000:.2f}s")

    nuevos_tracks = []
    for track in data.get("tracks", []):
        ttype = track.get("type")
        if ttype in ("video", "audio", "text"):
            nuevo_track = procesar_track(track, materiales_by_id, origen_lista_by_id, clonar_materiales=True)
        else:
            # Tipo de track no esperado: lo dejamos pasar intacto para no
            # perder informacion, pero avisamos.
            print(f"AVISO: track de tipo desconocido '{ttype}', se deja intacto")
            nuevo_track = copy.deepcopy(track)
        nuevos_tracks.append(nuevo_track)

    # --- Cartel fijo nuevo ---
    # Molde de estilo: la palabra "Bien" del track karaoke estandar
    # (size 10, Poppins-Bold, sombra calibrada) - mismo criterio que use el
    # resto del proyecto para no introducir un estilo nuevo sin calibrar.
    material_molde = None
    segmento_molde = None
    for t in data.get("tracks", []):
        if t.get("type") != "text":
            continue
        for seg in t.get("segments", []):
            mat = materiales_by_id.get(seg.get("material_id"))
            if mat and mat.get("content") and json.loads(mat["content"]).get("text", "").strip() == "Bien":
                material_molde = mat
                segmento_molde = seg
                break
        if material_molde is not None:
            break
    if material_molde is None:
        # Fallback: cualquier material/segmento de texto karaoke sirve como molde
        for t in data.get("tracks", []):
            if t.get("type") == "text" and t.get("segments"):
                segmento_molde = t["segments"][0]
                material_molde = materiales_by_id.get(segmento_molde.get("material_id"))
                break
        print("AVISO: no se encontro el molde 'Bien', se uso otro material/segmento como base de estilo")

    material_cartel, material_id_cartel = construir_material_cartel(material_molde)
    materiales_by_id[material_cartel["id"]] = material_cartel
    origen_lista_by_id[material_cartel["id"]] = "texts"
    track_cartel = construir_track_cartel(material_id_cartel, duracion_total_us, segmento_molde)
    nuevos_tracks.append(track_cartel)

    # --- Reconstruir las listas de materials, repartiendo cada material
    #     (incluidos los clones del HOOK y el cartel nuevo) a la lista de
    #     origen que tenia ANTES (texts / videos / audios / etc), para no
    #     mover nada a una lista incorrecta. Las listas de material que no
    #     tocamos (canvases, transitions, speeds, etc.) quedan intactas. ---
    for tipo in TIPOS_MATERIAL_RELEVANTES:
        materials[tipo] = [
            m for mid, m in materiales_by_id.items()
            if origen_lista_by_id.get(mid) == tipo
        ]

    data["materials"] = materials
    data["tracks"] = nuevos_tracks
    data["duration"] = duracion_total_us

    with open(RUTA_JSON_SALIDA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Listo. Archivo nuevo escrito en: {RUTA_JSON_SALIDA}")
    print(f"Cantidad de tracks: {len(nuevos_tracks)}")
    for i, t in enumerate(nuevos_tracks):
        print(f"  [{i}] type={t.get('type')} name={t.get('name')!r} segments={len(t.get('segments', []))}")


if __name__ == "__main__":
    main()

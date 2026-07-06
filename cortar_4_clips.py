# =====================================================================
# Script para CORTAR el video "entrv señores" en 4 clips independientes
# y crear 4 carpetas de proyecto NUEVAS en CapCut, una por clip.
# =====================================================================
# QUE HACE:
#   1. Lee el draft original "entrv señores" (video + 98 segmentos de
#      auto-caption).
#   2. Para cada uno de los 4 rangos definidos en RANGOS_CLIPS:
#      - Recorta el segmento de video a ese rango exacto.
#      - Filtra los segmentos de texto/auto-caption que caen DENTRO de
#        ese rango (descartando los que quedan afuera), y les resta el
#        offset para que la timeline nueva arranque en 0.
#      - Ajusta la duracion total del draft a la duracion del recorte.
#      - Copia TODA la carpeta del proyecto original a una carpeta
#        nueva (mismo nombre + sufijo del clip), y le reemplaza el
#        draft_content.json por el recortado.
#   3. El video/audio fuente (.mov) NO se copia ni se modifica - el
#      draft nuevo sigue apuntando al mismo archivo por su ruta
#      absoluta, CapCut lo recorta visualmente segun el nuevo rango.
#
# NO TOCA stickers, transiciones, ni nada visual nuevo - eso lo seguis
# agregando vos a mano en cada proyecto despues de correr este script.
#
# IMPORTANTE: CapCut tiene que estar CERRADO mientras corre esto.
# =====================================================================

import json
import os
import shutil
import copy

# =====================================================================
# PASO A - CONFIGURACION
# =====================================================================

CARPETA_DRAFTS = r"C:\Users\user2\AppData\Local\CapCut\User Data\Projects\com.lveditor.draft"
NOMBRE_DRAFT_ORIGINAL = "entrv señores"

# Si ya tenes el draft_content.json del original en tu carpeta de
# trabajo (lo que normalmente vas a tener, porque ya me lo pasaste),
# el script lo usa directo de ahi en vez de ir a buscarlo a CapCut.
# Si no existe localmente, lo lee de CARPETA_DRAFTS/NOMBRE_DRAFT_ORIGINAL.
RUTA_JSON_LOCAL_OPCIONAL = "draft_entrv_señores.json"

# Rangos confirmados, en MICROSEGUNDOS exactos (mismos valores que ya
# extrajimos de las 98 oraciones reales del auto-caption - no
# redondeados a 2 decimales como en el guion en segundos, para que el
# primer/ultimo segmento de texto de cada clip no se pierda por error
# de redondeo). Con margen de 1000us (1ms) hacia afuera en cada borde,
# asi el segmento que define el limite siempre entra completo.
# Cada tupla es (nombre_sufijo, inicio_us, fin_us).
MARGEN_US = 1000

RANGOS_CLIPS = [
    ("clip1_serge",          266666 - MARGEN_US,    65813333 + MARGEN_US),
    ("clip2_fantastica",     74000000 - MARGEN_US,  106226666 + MARGEN_US),
    ("clip3_elogios",        120800000 - MARGEN_US, 158853333 + MARGEN_US),
    ("clip4_estribo_futbol", 159333333 - MARGEN_US, 202386666 + MARGEN_US),
]

# =====================================================================
# PASO B - FUNCIONES DE CORTE
# =====================================================================

def cargar_draft_original():
    if os.path.exists(RUTA_JSON_LOCAL_OPCIONAL):
        ruta = RUTA_JSON_LOCAL_OPCIONAL
    else:
        ruta = os.path.join(CARPETA_DRAFTS, NOMBRE_DRAFT_ORIGINAL, "draft_content.json")

    if not os.path.exists(ruta):
        raise SystemExit(
            f"No encontre el draft original en ninguna de estas rutas:\n"
            f"  - {RUTA_JSON_LOCAL_OPCIONAL}\n"
            f"  - {os.path.join(CARPETA_DRAFTS, NOMBRE_DRAFT_ORIGINAL, 'draft_content.json')}\n"
            "Confirma que el archivo este en tu carpeta de trabajo o que "
            "el nombre del draft original sea correcto."
        )

    print(f"Cargando draft original desde: {ruta}")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def recortar_segmento_video(seg_video, inicio_us, fin_us):
    """Recorta el (unico) segmento de video al rango [inicio_us, fin_us).
    target_timerange queda en 0 (arranca la timeline nueva desde el
    principio). source_timerange se desplaza para tomar el tramo
    correcto del archivo fuente original."""
    seg = copy.deepcopy(seg_video)
    duracion_nueva = fin_us - inicio_us

    src = seg["source_timerange"]
    # el inicio real dentro del archivo fuente = inicio original del
    # segmento + el offset que estamos recortando
    src_start_nuevo = src["start"] + inicio_us
    seg["source_timerange"] = {"start": src_start_nuevo, "duration": duracion_nueva}
    seg["target_timerange"] = {"start": 0, "duration": duracion_nueva}
    return seg


def filtrar_y_desplazar_segmentos_texto(segments_texto, inicio_us, fin_us):
    """Devuelve solo los segmentos de texto cuyo target_timerange cae
    COMPLETAMENTE dentro de [inicio_us, fin_us), con su start
    desplazado para que la nueva timeline arranque en 0.

    Un segmento que arranca antes del corte o termina despues del corte
    se descarta entero (no se recorta a la mitad) para no generar
    palabras truncadas a mitad de frase - el guion ya fue armado
    eligiendo limites que caen en limites reales de oracion."""
    resultado = []
    for seg in segments_texto:
        tr = seg["target_timerange"]
        seg_start = tr["start"]
        seg_end = tr["start"] + tr["duration"]

        if seg_start >= inicio_us and seg_end <= fin_us:
            nuevo = copy.deepcopy(seg)
            nuevo["target_timerange"] = {
                "start": seg_start - inicio_us,
                "duration": tr["duration"],
            }
            resultado.append(nuevo)
    return resultado


def construir_draft_recortado(data_original, inicio_us, fin_us):
    duracion_us = fin_us - inicio_us

    data = copy.deepcopy(data_original)

    tracks_nuevos = []
    ids_texto_usados = set()
    for track in data["tracks"]:
        if track["type"] == "video":
            seg_original = track["segments"][0]
            track["segments"] = [recortar_segmento_video(seg_original, inicio_us, fin_us)]
            tracks_nuevos.append(track)
        elif track["type"] == "text":
            track["segments"] = filtrar_y_desplazar_segmentos_texto(
                track["segments"], inicio_us, fin_us
            )
            for s in track["segments"]:
                ids_texto_usados.add(s["material_id"])
            tracks_nuevos.append(track)
        else:
            # cualquier otro tipo de track (no deberia haber en este
            # draft, pero por si acaso no se descarta silenciosamente)
            tracks_nuevos.append(track)

    data["tracks"] = tracks_nuevos
    data["duration"] = duracion_us

    # Limpiar de materials.texts los materiales de texto que quedaron
    # fuera del rango (no es obligatorio para que CapCut abra el
    # archivo, pero evita arrastrar 98 materiales cuando solo se usan
    # ~15-25 por clip).
    if "materials" in data and "texts" in data["materials"]:
        data["materials"]["texts"] = [
            m for m in data["materials"]["texts"] if m["id"] in ids_texto_usados
        ]

    return data, len(ids_texto_usados)


def crear_carpeta_proyecto_nueva(sufijo, draft_data):
    carpeta_origen = os.path.join(CARPETA_DRAFTS, NOMBRE_DRAFT_ORIGINAL)
    carpeta_destino = os.path.join(CARPETA_DRAFTS, f"{NOMBRE_DRAFT_ORIGINAL} - {sufijo}")

    if os.path.exists(carpeta_destino):
        raise SystemExit(
            f"Ya existe una carpeta de proyecto en:\n  {carpeta_destino}\n"
            "Para no pisar un draft existente, este script no continua. "
            "Borrala a mano en CapCut (o renombrala) si querias regenerarla."
        )

    if not os.path.exists(carpeta_origen):
        raise SystemExit(
            f"No encontre la carpeta del proyecto original en:\n  {carpeta_origen}\n"
            "Sin esa carpeta no puedo copiar draft_meta_info.json ni los "
            "demas archivos auxiliares que CapCut necesita."
        )

    shutil.copytree(carpeta_origen, carpeta_destino)

    ruta_json_destino = os.path.join(carpeta_destino, "draft_content.json")
    with open(ruta_json_destino, "w", encoding="utf-8") as f:
        json.dump(draft_data, f, ensure_ascii=False)

    # Actualizar el nombre dentro de draft_meta_info.json si existe,
    # para que CapCut muestre el nombre correcto en la lista de
    # proyectos (no estrictamente necesario, pero evita confusion).
    ruta_meta = os.path.join(carpeta_destino, "draft_meta_info.json")
    if os.path.exists(ruta_meta):
        try:
            with open(ruta_meta, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if "draft_name" in meta:
                meta["draft_name"] = f"{NOMBRE_DRAFT_ORIGINAL} - {sufijo}"
            with open(ruta_meta, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False)
        except Exception as e:
            print(f"  (aviso: no se pudo actualizar draft_meta_info.json: {e})")

    return carpeta_destino


# =====================================================================
# PASO C - EJECUCION
# =====================================================================

def main():
    data_original = cargar_draft_original()
    duracion_original_seg = data_original.get("duration", 0) / 1_000_000
    print(f"Duracion del draft original: {duracion_original_seg:.2f}s")
    print()

    for sufijo, inicio_us, fin_us in RANGOS_CLIPS:
        inicio_seg_disp = inicio_us / 1_000_000
        fin_seg_disp = fin_us / 1_000_000
        print(f"--- Procesando {sufijo} ({inicio_seg_disp:.2f}s - {fin_seg_disp:.2f}s) ---")

        if fin_us > data_original.get("duration", 0):
            raise SystemExit(
                f"El rango de '{sufijo}' termina en {fin_seg_disp:.2f}s pero el "
                f"video original dura solo {duracion_original_seg:.2f}s. "
                "Revisa RANGOS_CLIPS."
            )

        draft_recortado, n_oraciones = construir_draft_recortado(
            data_original, inicio_us, fin_us
        )
        duracion_nueva = draft_recortado["duration"] / 1_000_000
        print(f"  Duracion del clip: {duracion_nueva:.2f}s")
        print(f"  Segmentos de auto-caption conservados: {n_oraciones}")

        carpeta_destino = crear_carpeta_proyecto_nueva(sufijo, draft_recortado)
        print(f"  Carpeta de proyecto creada en:\n    {carpeta_destino}")
        print()

    print("Listo. Los 4 proyectos nuevos ya estan en tu carpeta de CapCut.")
    print("Abri CapCut: deberian aparecer como 4 proyectos nuevos en la lista,")
    print(f'llamados "{NOMBRE_DRAFT_ORIGINAL} - <sufijo>".')
    print()
    print("Revisa cada uno: video recortado al rango correcto, y el texto del")
    print("auto-caption presente solo donde corresponde (todavia sin estilo -")
    print("eso se hace en el siguiente paso con generar_subtitulos).")


if __name__ == "__main__":
    main()

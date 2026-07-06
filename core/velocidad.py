"""
Acelerador de pausas: en vez de ELIMINAR las pausas del habla, las corta
y las acelera (speed ramp), comprimiendo el tiempo muerto sin perder
continuidad visual.

Mecanica sobre el draft_content.json real de CapCut (verificada contra
draft real):
  - Cada segmento tiene target_timerange/source_timerange (microsegundos),
    un campo speed, y una referencia en extra_material_refs a un material
    de materials.speeds ({type:"speed", speed, curve_speed}).
  - Para acelerar una pausa [p1,p2] a velocidad k:
      1. Se parte el segmento de video que la contiene en 3 (antes /
         pausa / despues), duplicando TODOS sus materiales referenciados
         con IDs nuevos (leccion del handoff: CapCut descarta en silencio
         lo que referencia materiales invalidos).
      2. El segmento del medio queda con speed=k y duracion target
         (p2-p1)/k.
      3. TODO lo que empieza despues de p2, en TODOS los tracks (video,
         audio, texto), se corre hacia atras por el tiempo ahorrado
         (ripple). Asi los captions siguen sincronizados.
      4. Los timestamps por-palabra de los materiales de texto (words)
         tambien se corren, para que la generacion de subtitulos karaoke
         posterior siga alineada. Soporta ambos formatos (viejo: us
         dentro de content; nuevo 8.8+: ms a nivel raiz).
      5. draft["duration"] se reduce por el total ahorrado.

Limitaciones (a proposito, para no romper drafts complejos):
  - El segmento a partir debe tener speed=1.0 y sin keyframes.
  - Si un segmento de OTRO track se superpone parcialmente con la pausa
    (ej: musica de fondo que la atraviesa), se aborta con un mensaje
    claro, salvo --forzar (que lo deja intacto sin ripple).

NOTA sobre "curvas" reales (rampa suave de CapCut): el campo curve_speed
existe pero en todos los drafts analizados esta en null, asi que no hay
muestra real del schema. Para no inventarlo (y que CapCut lo descarte en
silencio), esta version usa velocidad CONSTANTE por pausa. Ver
calibrar_curva() abajo para el procedimiento de captura del schema real.
"""

import bisect
import copy
import json
import uuid
from pathlib import Path
from typing import List, Optional, Tuple


def _nuevo_id() -> str:
    return str(uuid.uuid4()).upper()


def calcular_velocidad_por_importancia(
    pausas: List[dict], oraciones: List[List[dict]],
    velocidad_min: float = 2.0, velocidad_max: float = 8.0,
) -> List[dict]:
    """Asigna una velocidad a cada pausa segun que tan "densa" es la
    ORACION QUE LA PRECEDE (la que hay que digerir antes de que arranque
    el silencio):

      - Frase previa con MUCHAS palabras (densa/importante) -> velocidad
        cerca de velocidad_min: se acelera POCO, dando tiempo a asimilar.
      - Frase previa CORTA (interjeccion, relleno) -> velocidad cerca de
        velocidad_max: se acelera FUERTE, esa pausa importa menos.

    La densidad se mide en PERCENTIL relativo a las demas oraciones del
    MISMO draft (no un umbral fijo), porque "una frase larga" varia segun
    el video: en una entrevista tecnica todas son largas, en un video
    corto una de 5 palabras ya puede ser la mas densa.

    Pausas de inicio/fin de video (sin oracion que proteger de un lado)
    van siempre a velocidad_max.
    """
    info_oraciones = [
        (o[-1]["end_us"] / 1e6, len(o)) for o in oraciones if o
    ]
    if not info_oraciones:
        return [{**p, "velocidad": velocidad_max} for p in pausas]

    conteos = sorted(n for _, n in info_oraciones)

    def percentil(n: int) -> float:
        if len(conteos) <= 1:
            return 0.5
        idx = bisect.bisect_left(conteos, n)
        return idx / (len(conteos) - 1)

    resultado = []
    for p in pausas:
        if p["tipo"] != "entre_frases":
            resultado.append({**p, "velocidad": velocidad_max})
            continue
        # Oracion cuyo final coincide con el arranque de esta pausa
        oracion_previa = min(info_oraciones, key=lambda x: abs(x[0] - p["inicio"]))
        pct = percentil(oracion_previa[1])
        vel = velocidad_max - pct * (velocidad_max - velocidad_min)
        resultado.append({
            **p, "velocidad": round(vel, 2),
            "palabras_frase_previa": oracion_previa[1],
        })
    return resultado


class PausaNoAplicable(Exception):
    pass


class AceleradorPausas:

    def __init__(self, draft_json_path):
        self.path = Path(draft_json_path)
        with open(self.path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self._indexar_materiales()

    # -- indexado ------------------------------------------------------------

    def _indexar_materiales(self):
        """id -> (lista_de_materials, indice) para poder duplicar refs."""
        self._mat_index = {}
        for categoria, lista in (self.data.get("materials") or {}).items():
            if not isinstance(lista, list):
                continue
            for m in lista:
                if isinstance(m, dict) and m.get("id"):
                    self._mat_index[m["id"]] = (lista, m)

    def _duplicar_material(self, mat_id: str) -> Optional[str]:
        """Duplica un material con ID nuevo y lo agrega a su lista.
        Devuelve el ID nuevo (o None si el material no existe)."""
        entry = self._mat_index.get(mat_id)
        if entry is None:
            return None
        lista, mat = entry
        nuevo = copy.deepcopy(mat)
        nuevo["id"] = _nuevo_id()
        lista.append(nuevo)
        self._mat_index[nuevo["id"]] = (lista, nuevo)
        return nuevo["id"]

    def _clonar_segmento(self, seg: dict) -> dict:
        """Copia profunda de un segmento con ID nuevo y TODOS sus
        extra_material_refs duplicados (evita refs compartidas que CapCut
        pueda rechazar). El material principal (material_id: el video en
        si) NO se duplica: es legitimo que varios segmentos usen el mismo
        archivo de video."""
        nuevo = copy.deepcopy(seg)
        nuevo["id"] = _nuevo_id()
        refs_nuevas = []
        for ref in seg.get("extra_material_refs", []) or []:
            dup = self._duplicar_material(ref)
            refs_nuevas.append(dup if dup else ref)
        nuevo["extra_material_refs"] = refs_nuevas
        return nuevo

    def _set_speed(self, seg: dict, velocidad: float):
        """Fija speed en el segmento Y en su material de speed asociado."""
        seg["speed"] = float(velocidad)
        for ref in seg.get("extra_material_refs", []) or []:
            entry = self._mat_index.get(ref)
            if entry and entry[1].get("type") == "speed":
                entry[1]["speed"] = float(velocidad)
                return
        # Sin material de speed referenciado: crear uno y referenciarlo
        speeds = self.data["materials"].setdefault("speeds", [])
        nuevo = {"id": _nuevo_id(), "type": "speed", "mode": 0,
                 "speed": float(velocidad), "curve_speed": None}
        speeds.append(nuevo)
        self._mat_index[nuevo["id"]] = (speeds, nuevo)
        seg.setdefault("extra_material_refs", []).append(nuevo["id"])

    # -- nucleo --------------------------------------------------------------

    def _segmentos_en_rango(self, track: dict, p1: int, p2: int) -> List[int]:
        """Indices (en orden) de los segmentos del track que se
        SUPERPONEN con [p1,p2). Puede ser 1 o varios: si el video ya
        tenia cortes existentes dentro de la pausa (comun en material
        real ya editado - zooms, color grading, transiciones), la pausa
        cae sobre mas de un segmento."""
        indices = []
        for i, seg in enumerate(track.get("segments", [])):
            t = seg.get("target_timerange") or {}
            ini, dur = int(t.get("start", 0)), int(t.get("duration", 0))
            fin = ini + dur
            if fin > p1 and ini < p2:
                indices.append(i)
        return indices

    def _partir_y_acelerar(self, track: dict, indices: List[int],
                           p1: int, p2: int, velocidad: float) -> Tuple[int, List[str]]:
        """Recorta cada segmento involucrado a su porcion antes/dentro/
        despues de la pausa; la porcion DENTRO de cada uno se acelera
        (mismo factor). Soporta 1 o varios segmentos preexistentes
        cubriendo la pausa. Devuelve el tiempo ahorrado en us."""
        segs = [track["segments"][i] for i in indices]
        for seg in segs:
            if abs(float(seg.get("speed", 1.0)) - 1.0) > 1e-6:
                raise PausaNoAplicable(
                    "un segmento dentro de la pausa ya tiene velocidad != 1.0")
            if seg.get("common_keyframes"):
                raise PausaNoAplicable(
                    "un segmento dentro de la pausa tiene keyframes "
                    "(color/efectos) - no se puede partir con seguridad")

        piezas = []
        cursor_target = None  # posicion donde arranca la proxima pieza
        ahorro_total = 0

        for seg in segs:
            t = seg["target_timerange"]
            s = seg["source_timerange"]
            t_ini, t_dur = int(t["start"]), int(t["duration"])
            s_ini = int(s["start"])
            t_fin = t_ini + t_dur

            if cursor_target is None:
                cursor_target = t_ini

            # Parte ANTES de la pausa (solo puede existir en el PRIMER
            # segmento involucrado, si arranca antes de p1)
            ini_pausa_local = max(t_ini, p1)
            if t_ini < ini_pausa_local:
                dur_antes = ini_pausa_local - t_ini
                a = self._clonar_segmento(seg)
                a["target_timerange"] = {"start": cursor_target, "duration": dur_antes}
                a["source_timerange"] = {"start": s_ini, "duration": dur_antes}
                piezas.append(a)
                cursor_target += dur_antes

            # Parte DENTRO de la pausa (la porcion de ESTE segmento que
            # cae en [p1,p2)) - se acelera
            fin_pausa_local = min(t_fin, p2)
            dur_dentro = fin_pausa_local - ini_pausa_local
            if dur_dentro > 0:
                offset_dentro = ini_pausa_local - t_ini
                dur_acelerada = int(round(dur_dentro / velocidad))
                m = self._clonar_segmento(seg)
                m["target_timerange"] = {"start": cursor_target, "duration": dur_acelerada}
                m["source_timerange"] = {"start": s_ini + offset_dentro, "duration": dur_dentro}
                self._set_speed(m, velocidad)
                piezas.append(m)
                cursor_target += dur_acelerada
                ahorro_total += dur_dentro - dur_acelerada

            # Parte DESPUES de la pausa (solo puede existir en el
            # ULTIMO segmento involucrado, si termina despues de p2)
            if t_fin > fin_pausa_local:
                dur_despues = t_fin - fin_pausa_local
                offset_despues = fin_pausa_local - t_ini
                d = self._clonar_segmento(seg)
                d["target_timerange"] = {"start": cursor_target, "duration": dur_despues}
                d["source_timerange"] = {"start": s_ini + offset_despues, "duration": dur_despues}
                piezas.append(d)
                cursor_target += dur_despues

        track["segments"][indices[0]:indices[-1] + 1] = piezas
        return ahorro_total, [p["id"] for p in piezas]

    def _ripple(self, desde_us: int, ahorro_us: int, excluir_ids: set,
                forzar: bool):
        """Corre hacia atras todo segmento que empiece en/despues de
        desde_us, en todos los tracks. Detecta superposiciones parciales."""
        for track in self.data.get("tracks", []):
            for seg in track.get("segments", []):
                if seg.get("id") in excluir_ids:
                    continue
                t = seg.get("target_timerange") or {}
                ini = int(t.get("start", 0))
                fin = ini + int(t.get("duration", 0))
                if ini >= desde_us:
                    t["start"] = ini - ahorro_us
                elif fin > desde_us:
                    # se superpone parcialmente con la zona comprimida
                    if not forzar:
                        raise PausaNoAplicable(
                            f"un segmento del track '{track.get('type')}' "
                            f"({ini/1e6:.1f}s-{fin/1e6:.1f}s) atraviesa la "
                            "pausa. Usa --forzar para dejarlo intacto "
                            "(puede desincronizarse levemente).")

    def _shift_words(self, desde_us: int, ahorro_us: int):
        """Corre los timestamps por-palabra de los materiales de texto,
        en ambos formatos, para que el generador karaoke siga alineado."""
        for mat in (self.data.get("materials") or {}).get("texts", []) or []:
            # Formato nuevo (8.8+): arrays paralelos a nivel raiz, en MS
            w = mat.get("words")
            if isinstance(w, dict) and w.get("text"):
                desde_ms, ahorro_ms = desde_us // 1000, ahorro_us // 1000
                for key in ("start_time", "end_time"):
                    w[key] = [v - ahorro_ms if isinstance(v, (int, float))
                              and v >= desde_ms else v
                              for v in (w.get(key) or [])]
            # Formato viejo: words dentro de content (JSON string), en US
            content = mat.get("content")
            if isinstance(content, str) and '"words"' in content:
                try:
                    obj = json.loads(content)
                except Exception:
                    continue
                cambiado = False
                for palabra in obj.get("words", []) or []:
                    for key in ("start_time", "end_time", "start_us", "end_us"):
                        v = palabra.get(key)
                        if isinstance(v, (int, float)) and v >= desde_us:
                            palabra[key] = v - ahorro_us
                            cambiado = True
                if cambiado:
                    mat["content"] = json.dumps(obj, ensure_ascii=False)

    # -- API publica ---------------------------------------------------------

    def acelerar_pausas(self, pausas: List[dict], velocidad: Optional[float] = None,
                        forzar: bool = False) -> dict:
        """Aplica la aceleracion a una lista de pausas ({inicio,fin} en
        SEGUNDOS, como las devuelve detectar_pausas_habla). Si cada pausa
        trae su propia clave 'velocidad' (ver calcular_velocidad_por_
        importancia), se usa esa; si no, se usa el parametro velocidad
        como valor unico para todas. Procesa de atras hacia adelante para
        que el ripple de una no corra los timestamps de las siguientes."""
        video_tracks = [t for t in self.data.get("tracks", [])
                        if t.get("type") == "video"]
        if not video_tracks:
            raise PausaNoAplicable("el draft no tiene tracks de video")

        aplicadas, saltadas, ahorro_total = [], [], 0
        for p in sorted(pausas, key=lambda x: -x["inicio"]):
            vel = p.get("velocidad", velocidad)
            if vel is None:
                saltadas.append({**p, "motivo": "sin velocidad definida"})
                continue
            p1, p2 = int(p["inicio"] * 1e6), int(p["fin"] * 1e6)
            hecho = False
            for track in video_tracks:
                indices = self._segmentos_en_rango(track, p1, p2)
                if not indices:
                    continue
                try:
                    ahorro, nuevos_ids = self._partir_y_acelerar(
                        track, indices, p1, p2, vel)
                    self._ripple(p2, ahorro, set(nuevos_ids), forzar)
                    self._shift_words(p2, ahorro)
                    ahorro_total += ahorro
                    aplicadas.append(p)
                    hecho = True
                except PausaNoAplicable as e:
                    saltadas.append({**p, "motivo": str(e)})
                    hecho = True
                break
            if not hecho:
                saltadas.append({**p, "motivo":
                                 "ningun segmento de video la contiene"})

        if "duration" in self.data:
            self.data["duration"] = int(self.data["duration"]) - ahorro_total

        return {"aplicadas": len(aplicadas), "saltadas": saltadas,
                "ahorro_seg": ahorro_total / 1e6}

    def _partir_y_eliminar(self, track: dict, indices: List[int],
                           p1: int, p2: int) -> Tuple[int, List[str]]:
        """Como _partir_y_acelerar pero sin crear la porcion 'dentro':
        el tramo [p1,p2) se borra por completo (corte real)."""
        segs = [track["segments"][i] for i in indices]
        for seg in segs:
            if abs(float(seg.get("speed", 1.0)) - 1.0) > 1e-6:
                raise PausaNoAplicable(
                    "un segmento dentro de la pausa ya tiene velocidad != 1.0")
            if seg.get("common_keyframes"):
                raise PausaNoAplicable(
                    "un segmento dentro de la pausa tiene keyframes "
                    "(color/efectos) - no se puede partir con seguridad")

        piezas = []
        cursor_target = None
        ahorro_total = 0

        for seg in segs:
            t = seg["target_timerange"]
            s = seg["source_timerange"]
            t_ini, t_dur = int(t["start"]), int(t["duration"])
            s_ini = int(s["start"])
            t_fin = t_ini + t_dur

            if cursor_target is None:
                cursor_target = t_ini

            ini_pausa_local = max(t_ini, p1)
            if t_ini < ini_pausa_local:
                dur_antes = ini_pausa_local - t_ini
                a = self._clonar_segmento(seg)
                a["target_timerange"] = {"start": cursor_target, "duration": dur_antes}
                a["source_timerange"] = {"start": s_ini, "duration": dur_antes}
                piezas.append(a)
                cursor_target += dur_antes

            fin_pausa_local = min(t_fin, p2)
            ahorro_total += max(0, fin_pausa_local - ini_pausa_local)

            if t_fin > fin_pausa_local:
                dur_despues = t_fin - fin_pausa_local
                offset_despues = fin_pausa_local - t_ini
                d = self._clonar_segmento(seg)
                d["target_timerange"] = {"start": cursor_target, "duration": dur_despues}
                d["source_timerange"] = {"start": s_ini + offset_despues, "duration": dur_despues}
                piezas.append(d)
                cursor_target += dur_despues

        track["segments"][indices[0]:indices[-1] + 1] = piezas
        return ahorro_total, [p["id"] for p in piezas]

    def eliminar_pausas(self, pausas: List[dict], forzar: bool = False) -> dict:
        """Como acelerar_pausas pero BORRA el tramo en vez de acelerarlo
        (corte real: la timeline se acorta esa duracion exacta, sin dejar
        rastro del tramo). Mismo orden atras-hacia-adelante, mismo ripple
        en todos los tracks, mismo corrimiento de timestamps de palabras."""
        video_tracks = [t for t in self.data.get("tracks", [])
                        if t.get("type") == "video"]
        if not video_tracks:
            raise PausaNoAplicable("el draft no tiene tracks de video")

        aplicadas, saltadas, ahorro_total = [], [], 0
        for p in sorted(pausas, key=lambda x: -x["inicio"]):
            p1, p2 = int(p["inicio"] * 1e6), int(p["fin"] * 1e6)
            hecho = False
            for track in video_tracks:
                indices = self._segmentos_en_rango(track, p1, p2)
                if not indices:
                    continue
                try:
                    ahorro, nuevos_ids = self._partir_y_eliminar(track, indices, p1, p2)
                    self._ripple(p2, ahorro, set(nuevos_ids), forzar)
                    self._shift_words(p2, ahorro)
                    ahorro_total += ahorro
                    aplicadas.append(p)
                    hecho = True
                except PausaNoAplicable as e:
                    saltadas.append({**p, "motivo": str(e)})
                    hecho = True
                break
            if not hecho:
                saltadas.append({**p, "motivo":
                                 "ningun segmento de video la contiene"})

        if "duration" in self.data:
            self.data["duration"] = int(self.data["duration"]) - ahorro_total

        return {"aplicadas": len(aplicadas), "saltadas": saltadas,
                "ahorro_seg": ahorro_total / 1e6}

    def guardar(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)


def seleccionar_pausas_para_objetivo(
    pausas: List[dict], duracion_actual_seg: float,
    objetivo_min_seg: float, objetivo_max_seg: float,
) -> List[dict]:
    """Elige que pausas cortar (las mas largas primero) hasta que la
    duracion resultante caiga en [objetivo_min, objetivo_max]. Si cortar
    TODAS las pausas no alcanza el minimo, devuelve todas igual (el
    llamador debe avisar que no se llego al objetivo)."""
    ordenadas = sorted(pausas, key=lambda p: -p["duracion"])
    elegidas = []
    restante = duracion_actual_seg
    for p in ordenadas:
        if restante <= objetivo_max_seg:
            break
        elegidas.append(p)
        restante -= p["duracion"]
    return elegidas


def calibrar_curva(draft_json_path) -> Optional[dict]:
    """Busca en un draft un material de speed con curve_speed REAL (no
    null) y lo devuelve, para capturar el schema de las curvas de CapCut
    desde una muestra hecha a mano (mismo metodo que la calibracion de
    estilo del handoff, Error #4).

    Procedimiento: duplica un draft chico en CapCut, aplicale a mano UNA
    curva de velocidad personalizada a un clip, cerra CapCut, y corre
    esto sobre su draft_content.json."""
    with open(draft_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for sp in (data.get("materials") or {}).get("speeds", []) or []:
        if sp.get("curve_speed"):
            return sp
    return None

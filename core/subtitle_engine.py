"""
Motor de generación de subtítulos estilo karaoke acumulativo.

Usa la API correcta de pycapcut:
- TextSegment(text, timerange, style=TextStyle(...), clip_settings=ClipSettings(...))
- ClipSettings(transform_x, transform_y, scale_x, scale_y)
- TrackType.text para crear el track

Resuelve errores del handoff:
- Error #1: Usa load_template(), NO duplicate_as_template()
- Error #4: Inyecta text_size + scale + type:"subtitle" + sombras a nivel raíz
- Error #5: Anclas ±0.20 + clamp para no cortar palabras
- Error #6: Anti-colisión con bounding boxes simples
- Error #7: Split en bloques ≤5 palabras en pausas ≥60ms
- Error #9: Umbral ≥150ms para overlap real
"""

from typing import List, Dict, Tuple, Optional

try:
    import pycapcut as cc
    _PYCAPCUT_AVAILABLE = True
except ImportError:
    cc = None  # type: ignore[assignment]
    _PYCAPCUT_AVAILABLE = False


class SubtitleEngine:
    """Motor central de generación de subtítulos karaoke acumulativo."""

    # Constantes validadas por usuario (NO CAMBIAR)
    MAX_PALABRAS_POR_BLOQUE = 5
    PAUSA_MINIMA_SPLIT_US = 60_000      # 60ms para cortar en pausas naturales
    UMBRAL_OVERLAP_REAL_US = 150_000    # 150ms mínimo para considerar overlap real

    # Layout validado (zigzag centrado sutil)
    ANCLA_IZQUIERDA = -0.20
    ANCLA_DERECHA = 0.20
    ANCHO_POR_CARACTER = 0.15
    PASO_Y_CORTO = 0.05   # Palabras 1-3 letras
    PASO_Y_LARGO = 0.10   # Palabras 8+ letras

    # Prefijo de los tracks de subtitulos (se crean varios para no solapar
    # en el tiempo: equivalente a los AUTO_pos_N del sistema original)
    TRACK_PREFIX = "AUTO_sub_"

    def __init__(self, script, profile: dict):
        """Inicializa el motor con un script ya cargado.

        Args:
            script: objeto ScriptFile devuelto por DraftFolder.load_template()
            profile: diccionario con configuración de estilos (de settings.json)
        """
        self.script = script
        self.profile = profile
        self.max_palabras_por_bloque = int(
            profile.get("max_palabras_por_bloque", self.MAX_PALABRAS_POR_BLOQUE)
        )
        self.ancla_izquierda = float(profile.get("ancla_izquierda", self.ANCLA_IZQUIERDA))
        self.ancla_derecha = float(profile.get("ancla_derecha", self.ANCLA_DERECHA))
        self.ancho_por_caracter = float(profile.get("ancho_por_caracter", self.ANCHO_POR_CARACTER))

    # ── Fábrica de conveniencia ────────────────────────────────────────────────

    @classmethod
    def from_draft(cls, draft_folder: str, draft_name: str, profile: dict) -> "SubtitleEngine":
        """Carga el draft y crea el motor.

        ⚠️ CRÍTICO (Error #1): usa load_template, NO duplicate_as_template.

        Args:
            draft_folder: ruta de la carpeta de drafts de CapCut
            draft_name: nombre del draft (ej: "arrizzo 8")
            profile: diccionario con configuración de estilos
        """
        if not _PYCAPCUT_AVAILABLE:
            raise RuntimeError("pycapcut no está instalado. Ejecuta: pip install pycapcut")

        folder_obj = cc.DraftFolder(draft_folder)
        script = folder_obj.load_template(draft_name)
        return cls(script, profile)

    # ── Pipeline principal ─────────────────────────────────────────────────────

    def generate(self, oraciones_auto: List[List[dict]]) -> dict:
        """Pipeline completo de generación.

        Pasos:
        1. Detecta diálogo simultáneo (≥150ms overlap)
        2. Divide oraciones largas en bloques ≤5 palabras
        3. Calcula posiciones (X, Y) con anti-colisión
        4. Crea segmentos en CapCut
        5. Guarda el draft

        Args:
            oraciones_auto: lista de oraciones, cada una es lista de palabras
                [{"word": "hola", "start_us": 1000000, "end_us": 1500000}, ...]

        Returns:
            Dict con resultado de la generación
        """
        # 1. Detectar diálogo simultáneo
        pares_overlap = self._detectar_overlap_real(oraciones_auto)

        # 2. Dividir oraciones largas
        bloques = self._dividir_en_bloques(oraciones_auto, pares_overlap)

        # 3. Calcular posiciones
        posiciones = self._calcular_posiciones(bloques, pares_overlap)

        # 4. Crear segmentos repartidos en varios tracks (anti SegmentOverlap)
        total_palabras, total_tracks = self._crear_segmentos(bloques, posiciones)

        # 5. Guardar
        self.script.save()

        return {
            "success": True,
            "total_palabras": total_palabras,
            "total_bloques": len(bloques),
            "pares_overlap": len(pares_overlap),
            "total_tracks": total_tracks,
            "track_name": self.TRACK_PREFIX + "*",
        }

    # ── Lógica de overlap ──────────────────────────────────────────────────────

    def _detectar_overlap_real(self, oraciones: List[List[dict]]) -> List[Tuple[int, int]]:
        """Detecta solo overlaps reales (≥150ms).

        Resuelve Error #9: falsos positivos por imprecisión de CapCut.
        Solo considera overlap si supera umbral de 150ms.
        """
        pares = []

        for i in range(len(oraciones) - 1):
            fin_i = max(p["end_us"] for p in oraciones[i])
            inicio_j = min(p["start_us"] for p in oraciones[i + 1])

            overlap = fin_i - inicio_j

            if overlap >= self.UMBRAL_OVERLAP_REAL_US:
                pares.append((i, i + 1))

        return pares

    # ── División de bloques ────────────────────────────────────────────────────

    def _dividir_en_bloques(self, oraciones: List[List[dict]],
                            pares_overlap: List[Tuple[int, int]]) -> List[dict]:
        """Divide oraciones largas en bloques ≤5 palabras.

        Resuelve Error #7: geometría imposible de oraciones largas.
        Prioriza cortar en pausas naturales (≥60ms).
        """
        bloques = []

        for idx_or, oracion in enumerate(oraciones):
            es_overlap = any(idx_or in par for par in pares_overlap)

            max_palabras = getattr(self, "max_palabras_por_bloque", self.MAX_PALABRAS_POR_BLOQUE)
            if len(oracion) <= max_palabras:
                bloques.append({
                    "idx_oracion": idx_or,
                    "palabras": oracion,
                    "es_overlap": es_overlap,
                })
            else:
                bloques.extend(self._dividir_oracion(oracion, idx_or, es_overlap))

        return bloques

    def _dividir_oracion(self, oracion: List[dict], idx: int,
                         es_overlap: bool) -> List[dict]:
        """Divide una oración en bloques, priorizando pausas naturales."""
        bloques = []
        inicio = 0

        while inicio < len(oracion):
            max_palabras = getattr(self, "max_palabras_por_bloque", self.MAX_PALABRAS_POR_BLOQUE)
            fin = min(inicio + max_palabras, len(oracion))

            if fin < len(oracion):
                pausa_idx = self._buscar_pausa_para_corte(oracion, inicio, fin)
                if pausa_idx is not None:
                    fin = pausa_idx + 1

            bloques.append({
                "idx_oracion": idx,
                "palabras": oracion[inicio:fin],
                "es_overlap": es_overlap,
            })
            inicio = fin

        return bloques

    def _buscar_pausa_para_corte(self, oracion: List[dict], inicio: int,
                                 fin: int) -> Optional[int]:
        """Busca la pausa más grande cerca del límite para cortar ahí."""
        mejor_pausa = None
        mejor_duracion = self.PAUSA_MINIMA_SPLIT_US

        for i in range(max(inicio, fin - 2), fin - 1):
            if i + 1 < len(oracion):
                duracion = oracion[i + 1]["start_us"] - oracion[i]["end_us"]
                if duracion >= mejor_duracion:
                    mejor_duracion = duracion
                    mejor_pausa = i

        return mejor_pausa

    # ── Cálculo de posiciones ─────────────────────────────────────────────────

    def _calcular_posiciones(self, bloques: List[dict],
                             pares_overlap: List[Tuple[int, int]]) -> dict:
        """Calcula (X, Y) de cada palabra con anti-colisión.

        Resuelve Errores #5, #6, #10, #11:
        - Anclas ±0.20 + clamp para no cortar palabras
        - Anti-colisión simple pero efectiva
        - Espaciado vertical variable según largo de palabra
        """
        posiciones = {}  # palabra_id → (x, y)
        # cajas del ULTIMO bloque generado en cada zona de pantalla ("normal",
        # "arriba", "abajo"), junto con hasta cuando siguen visibles. Sirve
        # para no colocar el bloque siguiente encima si todavia se solapan
        # en tiempo (bug detectado: bloques consecutivos muy seguidos podian
        # quedar literalmente en la misma posicion por unos frames).
        ultimo_bloque_por_zona = {}  # zona -> (fin_visible_us, [cajas])

        for b_idx, bloque in enumerate(bloques):
            es_overlap_segundo = any(
                bloque["idx_oracion"] == par[1] for par in pares_overlap
            )

            if bloque["es_overlap"]:
                y_zona_min, y_zona_max = (-0.4, -0.05) if es_overlap_segundo else (0.05, 0.4)
                zona = "abajo" if es_overlap_segundo else "arriba"
            else:
                y_zona_min, y_zona_max = -0.4, 0.4
                zona = "normal"

            palabras_bloque = bloque["palabras"]
            inicio_bloque = int(palabras_bloque[0]["start_us"]) if palabras_bloque else 0
            fin_visible_bloque = int(palabras_bloque[-1]["end_us"]) if palabras_bloque else 0

            cajas_ocupadas = []
            anterior = ultimo_bloque_por_zona.get(zona)
            if anterior is not None:
                fin_anterior, cajas_anterior = anterior
                if fin_anterior > inicio_bloque:
                    # el bloque anterior en esta misma zona todavia esta
                    # visible cuando arranca este -> heredar sus cajas para
                    # que el anti-colision no se solape con el
                    cajas_ocupadas = list(cajas_anterior)
            y_actual = y_zona_min + 0.08

            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra = palabra_data["word"]
                ancho_por_caracter = getattr(self, "ancho_por_caracter", self.ANCHO_POR_CARACTER)
                ancho_palabra = len(palabra) * ancho_por_caracter

                ancla_izquierda = getattr(self, "ancla_izquierda", self.ANCLA_IZQUIERDA)
                ancla_derecha = getattr(self, "ancla_derecha", self.ANCLA_DERECHA)
                x = ancla_izquierda if i % 2 == 0 else ancla_derecha

                if len(palabra) >= 8:
                    x *= 0.5

                x = max(-0.45 + ancho_palabra / 2, min(0.45 - ancho_palabra / 2, x))

                intento = 0
                while intento < 5:
                    choca = False
                    for (cx, cy, cw) in cajas_ocupadas:
                        distancia_x = abs(x - cx)
                        distancia_y = abs(y_actual - cy)
                        min_dist_x = (ancho_palabra + cw) / 2 + 0.02
                        # debe ser MENOR que PASO_Y_CORTO (0.05): si no, hasta
                        # palabras correctamente espaciadas por el avance
                        # normal "chocan" y se reempujan entre si.
                        min_dist_y = 0.04

                        if distancia_x < min_dist_x and distancia_y < min_dist_y:
                            choca = True
                            break

                    if not choca:
                        break

                    # BUG corregido: antes restaba (empujaba hacia el techo
                    # de la zona, amontonando todo en un punto). El zigzag
                    # fluye hacia ABAJO en pantalla -> hay que sumar.
                    y_actual += 0.05
                    intento += 1

                palabra_id = f"{b_idx}_{bloque['idx_oracion']}_{i}"
                # clamp final: nunca fuera de la zona visible de pantalla
                y_guardado = max(y_zona_min, min(y_zona_max, y_actual))
                posiciones[palabra_id] = (x, y_guardado)
                cajas_ocupadas.append((x, y_guardado, ancho_palabra))

                paso = self.PASO_Y_CORTO if len(palabra) <= 3 else self.PASO_Y_LARGO
                y_actual += paso
                # clamp contra el PISO de la zona (y_zona_max es el limite de
                # abajo en este sistema, ya que Y crece hacia abajo en pantalla)
                y_actual = min(y_actual, y_zona_max - 0.08)

            # guardar el estado de este bloque para que el SIGUIENTE bloque
            # en la misma zona sepa que posiciones evitar si todavia se
            # solapan en tiempo (arregla colisiones entre bloques consecutivos
            # muy seguidos, detectado con datos reales)
            ultimo_bloque_por_zona[zona] = (fin_visible_bloque, cajas_ocupadas)

        return posiciones

    # ── Creación de segmentos ─────────────────────────────────────────────────

    def _asegurar_track(self, track_name: str) -> None:
        """Crea el track de texto si aún no existe en ninguna fuente."""
        # Revisar imported_tracks (los del JSON existente)
        for t in self.script.imported_tracks:
            if t.name == track_name:
                return
        # Revisar tracks nuevos de esta sesión
        if track_name in self.script.tracks:
            return
        self.script.add_track(cc.TrackType.text, track_name)

    def _crear_segmentos(self, bloques: List[dict], posiciones: dict):
        """Crea un TextSegment por palabra y los reparte en varios tracks.

        Por que multiples tracks: pycapcut prohibe dos segmentos solapados en
        el TIEMPO dentro de un mismo track (SegmentOverlap). Con el efecto
        acumulativo (cada palabra se queda hasta el fin de su bloque) las
        palabras de un bloque se solapan en el tiempo -> deben ir en tracks
        distintos. Ademas, el dialogo simultaneo solapa oraciones enteras.
        Reparto greedy: cada palabra al primer track que ya este libre.
        Esto replica los AUTO_pos_N del sistema original.
        """
        scale = self.profile.get("scale_x", 3.037)
        scale_y = self.profile.get("scale_y", scale)
        text_size = self.profile.get("text_size", 30)
        color_hex = self.profile.get("text_color", "#FFFFFF")
        color_rgb = self._hex_to_rgb(color_hex)
        bold = self.profile.get("bold", True)

        estilo = cc.TextStyle(size=text_size, align=1, color=color_rgb, bold=bold)

        # 1) construir todos los segmentos con timing ACUMULATIVO
        items = []  # (start_us, end_us, palabra, x, y)
        for b_idx, bloque in enumerate(bloques):
            palabras = bloque["palabras"]
            if not palabras:
                continue
            # el bloque entero permanece hasta que termina su ultima palabra
            block_end = int(palabras[-1]["end_us"])
            for i, palabra_data in enumerate(palabras):
                start_us = int(palabra_data["start_us"])
                end_us = max(block_end, start_us + 1_000)  # acumulativo
                palabra_id = f"{b_idx}_{bloque['idx_oracion']}_{i}"
                x, y = posiciones.get(palabra_id, (0.0, 0.0))
                items.append((start_us, end_us, palabra_data["word"], x, y))

        # 2) reparto greedy en tracks (cada item al primer track libre)
        items.sort(key=lambda t: t[0])
        track_fin = []      # fin del ultimo segmento por track
        asignacion = []     # indice de track por item
        for (start_us, end_us, *_r) in items:
            destino = None
            for ti, fin in enumerate(track_fin):
                if fin <= start_us:
                    destino = ti
                    break
            if destino is None:
                destino = len(track_fin)
                track_fin.append(0)
            track_fin[destino] = end_us
            asignacion.append(destino)

        total_tracks = len(track_fin)

        # 3) crear los tracks necesarios
        for ti in range(total_tracks):
            self.script.add_track(cc.TrackType.text, f"{self.TRACK_PREFIX}{ti}")

        # 4) crear y agregar los segmentos
        total_palabras = 0
        for (start_us, end_us, palabra, x, y), ti in zip(items, asignacion):
            clip = cc.ClipSettings(
                scale_x=scale, scale_y=scale_y, transform_x=x, transform_y=y,
            )
            segmento = cc.TextSegment(
                text=palabra,
                timerange=cc.Timerange(start_us, end_us - start_us),
                style=estilo,
                clip_settings=clip,
            )
            self.script.add_segment(segmento, f"{self.TRACK_PREFIX}{ti}")
            total_palabras += 1

        return total_palabras, total_tracks

    def _se_solapa(self, intervals: List[Tuple[int, int]], new_start: int, new_end: int) -> bool:
        """Devuelve True si el intervalo nuevo se solapa con alguno existente."""
        for start, end in intervals:
            if new_start < end and new_end > start:
                return True
        return False

    def _hex_to_rgb(self, hex_color: str) -> Tuple[float, float, float]:
        """Convierte color '#RRGGBB' a tupla (r, g, b) en rango [0, 1]."""
        return _hex_a_rgb(hex_color)


# ── Utilidades ────────────────────────────────────────────────────────────────

def _hex_a_rgb(hex_color: str) -> tuple:
    """Convierte color '#RRGGBB' a tupla (r, g, b) en rango [0, 1]."""
    hex_color = hex_color.lstrip("#")
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except (ValueError, IndexError):
        return (1.0, 1.0, 1.0)  # blanco por defecto

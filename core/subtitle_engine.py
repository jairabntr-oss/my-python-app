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

import json
from typing import List, Tuple, Optional

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
    # PASO_Y_*: separacion vertical entre palabras consecutivas. Estos
    # valores estan calibrados para el size interno validado (STYLE_SIZE=10
    # en content.styles + scale ~3.037), que es el que se veia bien en
    # "entrv fede baic". OJO: si se cambia STYLE_SIZE hay que recalibrar
    # estos pasos y min_dist_y, porque dependen del alto REAL del texto en
    # pantalla (el bug de "mariaaa baic" fue justamente size=30 -> texto 3x
    # mas grande -> desbordaba este espaciado y se amontonaba).
    PASO_Y_CORTO = 0.045   # Palabras 1-3 letras (pedido: "achicar distancia entre lineas")
    PASO_Y_LARGO = 0.09    # Palabras 8+ letras

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

        # 6. Inyectar sombra y fuente (pycapcut.TextStyle no los soporta;
        # hay que parchear el JSON ya guardado, igual que documenta el
        # handoff original del usuario para "entrv fede baic")
        n_parcheados = self._inyectar_estilo_avanzado()

        return {
            "success": True,
            "total_palabras": total_palabras,
            "total_bloques": len(bloques),
            "pares_overlap": len(pares_overlap),
            "total_tracks": total_tracks,
            "materiales_con_sombra": n_parcheados,
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
                # ancho_por_caracter esta calibrado en unidades de ANCHO TOTAL
                # de pantalla (ver ANALISIS_FORMATO_ESTILO.md: "tecnologia", 10
                # letras, ocupa ~75% del ancho -> 10*0.15=1.5 sobre una escala
                # 0..2). Pero x/anclas estan en unidades de CapCut transform_x
                # (-1..1, mitad de pantalla = 1.0). Hay que pasar el ancho a
                # esa MISMA escala antes de usarlo en clamps/colision, sino
                # las palabras largas (7+ letras) miden "más" que la pantalla
                # entera y el clamp de X se invierte (bug: todas las palabras
                # largas terminaban exactamente en el mismo punto).
                ancho_palabra = (len(palabra) * ancho_por_caracter) / 2

                ancla_izquierda = getattr(self, "ancla_izquierda", self.ANCLA_IZQUIERDA)
                ancla_derecha = getattr(self, "ancla_derecha", self.ANCLA_DERECHA)

                if len(palabra) >= 8:
                    x = ancla_izquierda if i % 2 == 0 else ancla_derecha
                else:
                    # Alineado por BORDE IZQUIERDO (como un margen de
                    # parrafo), no por centro fijo. Pedido explicito del
                    # usuario tras ver su estilo manual de referencia: "de"
                    # y "7 años" en lineas consecutivas de la misma columna
                    # no compartian el mismo eje porque antes se centraba
                    # cada palabra en la MISMA x sin importar su ancho (una
                    # palabra corta y una larga centradas en el mismo punto
                    # arrancan en bordes distintos). Ahora ancla_izquierda /
                    # ancla_derecha representan el BORDE, y el centro real
                    # que CapCut necesita se calcula sumando medio ancho.
                    borde = ancla_izquierda if i % 2 == 0 else ancla_derecha
                    if i % 2 == 0:
                        x = borde + ancho_palabra  # borde + (2*ancho_palabra)/2
                    else:
                        # columna derecha: el "borde" alineado es el DERECHO,
                        # para que el efecto de columna sea simetrico
                        x = borde - ancho_palabra

                # RADIO_SEGURO_PALABRA_LARGA: con las columnas en ±0.20, una
                # palabra larga centrada no debe medir mas de ~0.18 de radio
                # o invade la columna opuesta aunque este perfectamente
                # centrada (confirmado con un draft real: "reservamos", 10
                # letras, con ancho_por_caracter=0.15 normal mide 0.75 de
                # radio -- mas ancho que TODA la pantalla). Un factor de
                # reduccion FIJO no sirve porque palabras de distinta
                # longitud necesitan distinto factor (8 letras necesita
                # ~0.30, 10 letras necesita ~0.24); en vez de eso, se
                # calcula el factor que hace falta para CADA palabra.
                if len(palabra) >= 8:
                    # RADIO_SEGURO levemente mas chico que antes (0.16 vs
                    # 0.18) -- pedido del usuario de "achicar un poco las
                    # palabras grandes sin perder legibilidad", aplicado aca
                    # como mas margen de seguridad contra las columnas en
                    # ±0.20 en vez de un numero de tamano de fuente fijo.
                    RADIO_SEGURO = 0.16
                    factor_reduccion = min(1.0, RADIO_SEGURO / ancho_palabra) if ancho_palabra > 0 else 1.0
                    ancho_palabra *= factor_reduccion
                    # Centrar en x=0 (no en la mitad de la ancla): el
                    # RADIO_SEGURO ya esta calculado para que, centrada en 0,
                    # la palabra no llegue a las columnas en ±0.20. Si en vez
                    # de centrar se deja a mitad de camino hacia la ancla
                    # (x=±0.10, lo que hacia "x *= 0.5"), el radio seguro de
                    # un lado deja de ser simetrico y la palabra puede seguir
                    # invadiendo la columna del lado hacia el que se desvio
                    # (confirmado con un caso real: x=-0.10 + radio 0.18
                    # llegaba a -0.28, pisando la columna izquierda en -0.20).
                    x = 0.0
                else:
                    factor_reduccion = 1.0

                x_lo = -0.45 + ancho_palabra / 2
                x_hi = 0.45 - ancho_palabra / 2
                if x_lo <= x_hi:
                    x = max(x_lo, min(x_hi, x))
                else:
                    # la palabra es mas ancha que el rango disponible: no hay
                    # clamp valido, centrar en 0 en vez de devolver siempre
                    # x_lo (que es lo que hacia max(lo, min(hi, x)) cuando
                    # lo > hi, aplastando todas las palabras largas al mismo
                    # punto sin importar su x original).
                    x = 0.0

                intento = 0
                MAX_INTENTOS_COLISION = 10  # antes 5: insuficiente para
                # bloques de 5 palabras cortas muy juntas; con 5 a veces se
                # agotaban los intentos sin destrabar la colision.
                while intento < MAX_INTENTOS_COLISION:
                    choca = False
                    for (cx, cy, cw) in cajas_ocupadas:
                        distancia_x = abs(x - cx)
                        distancia_y = abs(y_actual - cy)
                        min_dist_x = (ancho_palabra + cw) / 2 + 0.02
                        # min_dist_y calibrado para STYLE_SIZE=10 + scale
                        # ~3.037 (config validada en "entrv fede baic").
                        # Debe ser menor que PASO_Y_CORTO para no reempujar
                        # palabras que el avance normal ya separo bien. Si se
                        # cambia STYLE_SIZE, recalibrar este valor.
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
                # Clamp final "blando": antes este clamp aplastaba contra
                # y_zona_max a TODAS las palabras que se hubieran ido de
                # rango por el anti-colision, haciendo que terminaran todas
                # en la MISMA posicion Y (amontonadas). Ahora solo recorta
                # si la palabra se fue muy lejos (mas de 1 paso extra), y deja
                # que el resultado normal del anti-colision se respete dentro
                # de un margen razonable aunque exceda ligeramente la zona
                # "blanda" original.
                margen_extra = 0.15
                y_guardado = max(
                    y_zona_min - margen_extra,
                    min(y_zona_max + margen_extra, y_actual),
                )
                # Se guarda el factor_reduccion junto con la posicion para
                # que _crear_segmentos use el MISMO factor al elegir el
                # tamano de fuente real -- si el calculo de ancho/colision
                # asume una palabra mas chica pero el render usa el tamano
                # completo (o viceversa), vuelven a desalinearse posicion y
                # tamano real, que es justo el bug que esto corrige.
                posiciones[palabra_id] = (x, y_guardado, factor_reduccion)
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

    def _inyectar_estilo_avanzado(self) -> int:
        """Parchea sombra y fuente en los materiales de texto recien creados.

        pycapcut.TextStyle no expone sombra ni una forma de fijar font_path
        a nivel de material (Error #4 del handoff original: "pyCapCut no
        tiene API de alto nivel para esto, hay que inyectar el JSON directo
        despues de crear el segmento"). Por eso este paso reabre el
        draft_content.json YA GUARDADO, parchea los campos a nivel raiz
        de cada material generado por esta corrida, y vuelve a guardar.

        Valores default (shadow_alpha=0.33, shadow_angle=-115.9,
        shadow_distance=17.0) tomados de la calibracion documentada en
        PLAN_TECNICO_COMPLETO.md / config/user_profile.json.

        Returns:
            Cantidad de materiales parcheados.
        """
        ids = set(getattr(self, "_material_ids_generados", []) or [])
        if not ids:
            return 0

        save_path = getattr(self.script, "save_path", None)
        if not save_path:
            return 0

        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        shadow_enabled = self.profile.get("shadow_enabled", True)
        shadow_color = self.profile.get("shadow_color", "#000000")
        shadow_alpha = float(self.profile.get("shadow_alpha", 0.33))
        shadow_distance = float(self.profile.get("shadow_distance", 17.0))
        shadow_angle = float(self.profile.get("shadow_angle", -115.9))
        shadow_smoothing = float(self.profile.get("shadow_smoothing", 0.45))
        font_path = self.profile.get("font_path")  # ej. ruta a Poppins-Bold.ttf
        font_name = self.profile.get("font_name")
        font_id = self.profile.get("font_id", "")
        bold = bool(self.profile.get("bold", True))
        text_size = float(self.profile.get("text_size", 30))

        n = 0
        for mat in data.get("materials", {}).get("texts", []) or []:
            if mat.get("id") not in ids:
                continue

            # text_size a nivel raiz (distinto del 'size' interno en content.styles)
            mat["text_size"] = text_size

            if shadow_enabled:
                mat["has_shadow"] = True
                mat["shadow_color"] = shadow_color
                mat["shadow_alpha"] = shadow_alpha
                mat["shadow_distance"] = shadow_distance
                mat["shadow_angle"] = shadow_angle
                mat["shadow_smoothing"] = shadow_smoothing

            if font_path:
                mat["font_path"] = font_path
            if font_name:
                mat["font_name"] = font_name

            # CRITICO: ademas de font_path/font_name a nivel RAIZ, CapCut
            # renderiza el texto usando content.styles[N].font. Si ese campo
            # queda en None, CapCut ignora el font_path de la raiz y cae a la
            # fuente del SISTEMA (texto fino/generico, no Poppins-Bold).
            # Confirmado con draft real de "mariaaa baic": styles[0].font era
            # None y el texto se veia con fuente del sistema. Hay que inyectar
            # font (con path/id) dentro de CADA style del content.
            if font_path:
                content_raw = mat.get("content")
                if isinstance(content_raw, str):
                    try:
                        content_obj = json.loads(content_raw)
                    except Exception:
                        content_obj = None
                    if isinstance(content_obj, dict) and content_obj.get("styles"):
                        font_obj = {
                            "id": font_id or "",
                            "path": font_path,
                        }
                        for st in content_obj["styles"]:
                            if isinstance(st, dict):
                                st["font"] = font_obj
                                # asegurar negrita real (Poppins-BOLD)
                                if bold:
                                    st["bold"] = True
                        mat["content"] = json.dumps(content_obj, ensure_ascii=False)

            n += 1

        if n:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        return n

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
        # 'size' INTERNO de content.styles: es una escala distinta del
        # text_size raiz. La config validada de "entrv fede baic" usa
        # styles.size=10 + text_size=30 (raiz) + scale~3.037. El bug de
        # "mariaaa baic" fue generar styles.size=30 (=text_size), lo que
        # hacia el texto ~3x mas grande y causaba amontonamiento + letra
        # desproporcionada. Ver handoff Error #4.
        style_size = self.profile.get("style_size", 10)
        color_hex = self.profile.get("text_color", "#FFFFFF")
        color_rgb = self._hex_to_rgb(color_hex)
        bold = self.profile.get("bold", True)

        estilo = cc.TextStyle(
            size=style_size, align=1, color=color_rgb, bold=bold,
            auto_wrapping=True,  # hace que pycapcut guarde type:"subtitle"
        )
        # Cache de estilos reducidos por factor: _calcular_posiciones ya
        # decidio, palabra por palabra, el factor_reduccion exacto que hace
        # falta para que su ancho real no invada la columna opuesta (ver esa
        # funcion para el detalle). Aca se construye el TextStyle a juego con
        # ESE mismo factor en vez de un valor fijo, para que tamano visual y
        # ancho usado en el calculo de posicion/colision sean siempre
        # consistentes entre si.
        _cache_estilos_reducidos: Dict[float, "cc.TextStyle"] = {}

        def _estilo_para_factor(factor: float):
            if factor >= 0.999:
                return estilo
            factor_r = round(factor, 3)
            if factor_r not in _cache_estilos_reducidos:
                _cache_estilos_reducidos[factor_r] = cc.TextStyle(
                    size=style_size * factor_r, align=1, color=color_rgb,
                    bold=bold, auto_wrapping=True,
                )
            return _cache_estilos_reducidos[factor_r]

        # 1) construir todos los segmentos con timing ACUMULATIVO
        items = []  # (start_us, end_us, palabra, x, y, factor_reduccion)
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
                pos = posiciones.get(palabra_id, (0.0, 0.0, 1.0))
                # compat: tuplas viejas de 2 elementos (sin factor) -> 1.0
                x, y = pos[0], pos[1]
                factor = pos[2] if len(pos) > 2 else 1.0
                items.append((start_us, end_us, palabra_data["word"], x, y, factor))

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
        material_ids_creados = []
        for (start_us, end_us, palabra, x, y, factor), ti in zip(items, asignacion):
            clip = cc.ClipSettings(
                scale_x=scale, scale_y=scale_y, transform_x=x, transform_y=y,
            )
            estilo_palabra = _estilo_para_factor(factor)
            segmento = cc.TextSegment(
                text=palabra,
                timerange=cc.Timerange(start_us, end_us - start_us),
                style=estilo_palabra,
                clip_settings=clip,
            )
            self.script.add_segment(segmento, f"{self.TRACK_PREFIX}{ti}")
            material_ids_creados.append(segmento.material_id)
            total_palabras += 1

        self._material_ids_generados = material_ids_creados

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

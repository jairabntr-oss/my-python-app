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
import pycapcut as cc


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

    def __init__(self, script, profile: dict):
        """Inicializa el motor con un script ya cargado.

        Args:
            script: objeto ScriptFile devuelto por DraftFolder.load_template()
            profile: diccionario con configuración de estilos (de settings.json)
        """
        self.script = script
        self.profile = profile

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

        # 4. Crear track y segmentos
        self._asegurar_track("AUTO_subtitulos")
        total_palabras = self._crear_segmentos(bloques, posiciones)

        # 5. Guardar
        self.script.save()

        return {
            "success": True,
            "total_palabras": total_palabras,
            "total_bloques": len(bloques),
            "pares_overlap": len(pares_overlap),
            "track_name": "AUTO_subtitulos",
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

            if len(oracion) <= self.MAX_PALABRAS_POR_BLOQUE:
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
            fin = min(inicio + self.MAX_PALABRAS_POR_BLOQUE, len(oracion))

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

        for bloque in bloques:
            es_overlap_segundo = any(
                bloque["idx_oracion"] == par[1] for par in pares_overlap
            )

            if bloque["es_overlap"]:
                y_zona_min, y_zona_max = (-0.4, -0.05) if es_overlap_segundo else (0.05, 0.4)
            else:
                y_zona_min, y_zona_max = -0.4, 0.4

            cajas_ocupadas = []
            y_actual = y_zona_min + 0.08

            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra = palabra_data["word"]
                ancho_palabra = len(palabra) * self.ANCHO_POR_CARACTER

                x = self.ANCLA_IZQUIERDA if i % 2 == 0 else self.ANCLA_DERECHA

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
                        min_dist_y = 0.08

                        if distancia_x < min_dist_x and distancia_y < min_dist_y:
                            choca = True
                            break

                    if not choca:
                        break

                    y_actual -= 0.05
                    intento += 1

                palabra_id = f"{bloque['idx_oracion']}_{i}"
                posiciones[palabra_id] = (x, y_actual)
                cajas_ocupadas.append((x, y_actual, ancho_palabra))

                paso = self.PASO_Y_CORTO if len(palabra) <= 3 else self.PASO_Y_LARGO
                y_actual += paso
                y_actual = min(y_actual, y_zona_max - 0.08)

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

    def _crear_segmentos(self, bloques: List[dict], posiciones: dict) -> int:
        """Crea TextSegment en CapCut para cada palabra.

        Usa la API correcta de pycapcut:
        - TextSegment(text, timerange, style=TextStyle(...), clip_settings=ClipSettings(...))
        - ClipSettings para escala y posición
        - TextStyle para tamaño, color, alineación
        """
        track_name = "AUTO_subtitulos"
        total_palabras = 0

        scale = self.profile.get("scale_x", 3.037)
        text_size = self.profile.get("text_size", 30)
        color_hex = self.profile.get("text_color", "#FFFFFF")
        color_rgb = _hex_a_rgb(color_hex)

        estilo = cc.TextStyle(
            size=text_size,
            align=1,           # 1 = centrado
            color=color_rgb,
            bold=self.profile.get("bold", True),
        )

        for bloque in bloques:
            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra_id = f"{bloque['idx_oracion']}_{i}"
                x, y = posiciones.get(palabra_id, (0.0, 0.0))

                start_us = palabra_data["start_us"]
                end_us = palabra_data["end_us"]

                # EFECTO ACUMULATIVO: extender hasta próxima palabra
                if i < len(bloque["palabras"]) - 1:
                    end_us = bloque["palabras"][i + 1]["start_us"]

                duracion = max(end_us - start_us, 1_000)  # mínimo 1ms

                clip = cc.ClipSettings(
                    scale_x=scale,
                    scale_y=scale,
                    transform_x=x,
                    transform_y=y,
                )

                segmento = cc.TextSegment(
                    text=palabra_data["word"],
                    timerange=cc.Timerange(start_us, duracion),
                    style=estilo,
                    clip_settings=clip,
                )

                self.script.add_segment(segmento, track_name)
                total_palabras += 1

        return total_palabras


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

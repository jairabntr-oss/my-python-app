"""
Motor de generación de subtítulos estilo karaoke acumulativo.

Resuelve errores del handoff:
- Error #1: Usa load_template(), NO duplicate_as_template()
- Error #4: Usa TextStyle + ClipSettings (API real de pycapcut)
- Error #5: Anclas ±0.20 + clamp para no cortar palabras
- Error #6: Anti-colisión con bounding boxes simples
- Error #7: Split en bloques ≤5 palabras en pausas ≥60ms
- Error #9: Umbral ≥150ms para overlap real
- Error #14: Distribución greedy en múltiples tracks para evitar SegmentOverlap
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
    
    def __init__(self, draft_folder: str, draft_name: str, profile: dict):
        """Inicializa el motor con un draft de CapCut.
        
        Args:
            draft_folder: ruta de la carpeta de drafts de CapCut
            draft_name: nombre del draft (ej: "tiggo 4", "arrizzo 8")
            profile: diccionario con configuración de estilos

        Raises:
            RuntimeError: si pycapcut no está instalado.
        """
        if not _PYCAPCUT_AVAILABLE:
            raise RuntimeError("pycapcut no está instalado. Ejecuta: pip install pycapcut")
        self.draft_folder = cc.DraftFolder(draft_folder)
        # ⚠️ CRÍTICO (Error #1): usar load_template, NO duplicate_as_template
        self.script = self.draft_folder.load_template(draft_name)
        self.profile = profile
    
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
                [{
                    "word": "hola",
                    "start_us": 1000000,
                    "end_us": 1500000
                }, ...]
        
        Returns:
            Dict con resultado de la generación
        """
        # 1. Detectar diálogo simultáneo
        pares_overlap = self._detectar_overlap_real(oraciones_auto)
        
        # 2. Dividir oraciones largas
        bloques = self._dividir_en_bloques(oraciones_auto, pares_overlap)
        
        # 3. Calcular posiciones
        posiciones = self._calcular_posiciones(bloques, pares_overlap)
        
        # 4. Crear segmentos
        total_palabras = self._crear_segmentos(bloques, posiciones, pares_overlap)
        
        # 5. Guardar
        self.script.save()
        
        return {
            "success": True,
            "total_palabras": total_palabras,
            "total_bloques": len(bloques),
            "pares_overlap": len(pares_overlap),
            "tracks": getattr(self, "_tracks_usados", []),
            "total_tracks": len(getattr(self, "_tracks_usados", [])),
        }
    
    def _detectar_overlap_real(self, oraciones: List[List[dict]]) -> List[Tuple[int, int]]:
        """Detecta solo overlaps reales (≥150ms).
        
        Resuelve Error #9: falsos positivos por imprecisión de CapCut.
        Solo considera overlap si supera umbral de 150ms.
        """
        pares = []
        
        for i in range(len(oraciones) - 1):
            # Fin de oración i
            fin_i = max(p["end_us"] for p in oraciones[i])
            # Inicio de oración i+1
            inicio_j = min(p["start_us"] for p in oraciones[i + 1])
            
            # Calcular overlap
            overlap = fin_i - inicio_j
            
            # Solo considerar si supera umbral
            if overlap >= self.UMBRAL_OVERLAP_REAL_US:
                pares.append((i, i + 1))
        
        return pares
    
    def _dividir_en_bloques(self, oraciones: List[List[dict]], 
                           pares_overlap: List[Tuple[int, int]]) -> List[dict]:
        """Divide oraciones largas en bloques ≤5 palabras.
        
        Resuelve Error #7: geometría imposible de oraciones largas.
        Prioriza cortar en pausas naturales (≥60ms).
        """
        bloques = []
        
        for idx_or, oracion in enumerate(oraciones):
            # Determinar si esta oración tiene overlap
            es_overlap = any(idx_or in par for par in pares_overlap)
            
            if len(oracion) <= self.MAX_PALABRAS_POR_BLOQUE:
                # Pequeña, agregar tal cual
                bloques.append({
                    "idx_oracion": idx_or,
                    "palabras": oracion,
                    "es_overlap": es_overlap
                })
            else:
                # Grande, dividir recursivamente
                bloques_or = self._dividir_oracion(oracion, idx_or, es_overlap)
                bloques.extend(bloques_or)
        
        return bloques
    
    def _dividir_oracion(self, oracion: List[dict], idx: int, 
                        es_overlap: bool) -> List[dict]:
        """Divide una oración en bloques, priorizando pausas naturales."""
        bloques = []
        inicio = 0
        
        while inicio < len(oracion):
            # Tomar máximo 5 palabras
            fin = min(inicio + self.MAX_PALABRAS_POR_BLOQUE, len(oracion))
            
            # Si no es el final, buscar pausa natural para cortar
            if fin < len(oracion):
                pausa_idx = self._buscar_pausa_para_corte(oracion, inicio, fin)
                if pausa_idx is not None:
                    fin = pausa_idx + 1
            
            bloque_palabras = oracion[inicio:fin]
            bloques.append({
                "idx_oracion": idx,
                "palabras": bloque_palabras,
                "es_overlap": es_overlap
            })
            
            inicio = fin
        
        return bloques
    
    def _buscar_pausa_para_corte(self, oracion: List[dict], inicio: int, 
                                fin: int) -> Optional[int]:
        """Busca la pausa más grande cerca del límite para cortar ahí."""
        mejor_pausa = None
        mejor_duracion = self.PAUSA_MINIMA_SPLIT_US
        
        # Buscar en últimas 2 palabras del bloque candidato
        for i in range(max(inicio, fin - 2), fin - 1):
            if i + 1 < len(oracion):
                duracion = oracion[i + 1]["start_us"] - oracion[i]["end_us"]
                if duracion >= mejor_duracion:
                    mejor_duracion = duracion
                    mejor_pausa = i
        
        return mejor_pausa
    
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
            # Determinar zona Y según overlap
            es_overlap_segundo = any(
                bloque["idx_oracion"] == par[1] for par in pares_overlap
            )
            
            if bloque["es_overlap"]:
                # Primer par: arriba, segundo par: abajo
                y_zona_min, y_zona_max = (-0.4, -0.05) if es_overlap_segundo else (0.05, 0.4)
            else:
                # Sin overlap: pantalla completa
                y_zona_min, y_zona_max = -0.4, 0.4
            
            # Limpiar cajas para este bloque
            cajas_ocupadas = []
            y_actual = y_zona_min + 0.08
            
            # Calcular posición de cada palabra
            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra = palabra_data["word"]
                ancho_palabra = len(palabra) * self.ANCHO_POR_CARACTER
                
                # Zigzag: alternar izquierda/derecha (Resuelve Error #5)
                x = self.ANCLA_IZQUIERDA if i % 2 == 0 else self.ANCLA_DERECHA
                
                # Palabras largas (8+ letras) se acercan 50% al centro
                if len(palabra) >= 8:
                    x *= 0.5
                
                # Clamp para no salir de pantalla (Resuelve Error #5)
                x = max(-0.45 + ancho_palabra/2, min(0.45 - ancho_palabra/2, x))
                
                # Anti-colisión simple (Resuelve Error #6)
                intento = 0
                while intento < 5:
                    choca = False
                    for (cx, cy, cw) in cajas_ocupadas:
                        # Verificar si choca
                        distancia_x = abs(x - cx)
                        distancia_y = abs(y_actual - cy)
                        min_dist_x = (ancho_palabra + cw) / 2 + 0.02
                        min_dist_y = 0.08
                        
                        if distancia_x < min_dist_x and distancia_y < min_dist_y:
                            choca = True
                            break
                    
                    if not choca:
                        break
                    
                    # Mover hacia arriba si choca
                    y_actual -= 0.05
                    intento += 1
                
                # Guardar posición
                palabra_id = f"{bloque['idx_oracion']}_{i}"
                posiciones[palabra_id] = (x, y_actual)
                cajas_ocupadas.append((x, y_actual, ancho_palabra))
                
                # Paso Y variable según largo de palabra
                paso = self.PASO_Y_CORTO if len(palabra) <= 3 else self.PASO_Y_LARGO
                y_actual += paso
                
                # Mantener dentro de la zona
                y_actual = min(y_actual, y_zona_max - 0.08)
        
        return posiciones
    
    def _crear_segmentos(self, bloques: List[dict], posiciones: dict,
                        pares_overlap: List[Tuple[int, int]]) -> int:
        """Crea TextSegment en CapCut para cada palabra usando la API real de pycapcut.

        Resuelve Error #4: usa TextStyle + ClipSettings (no TextMaterial ni add_material).
        Resuelve Error #14: distribuye en múltiples tracks (AUTO_subtitulos_1, _2, …) para
        evitar SegmentOverlap cuando el efecto acumulativo genera segmentos solapados en el tiempo.
        """
        # Recopilar datos de todos los segmentos
        segmentos_data = []
        for bloque in bloques:
            ultimo_end = bloque["palabras"][-1]["end_us"]
            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra_id = f"{bloque['idx_oracion']}_{i}"
                x, y = posiciones.get(palabra_id, (0, 0))
                start_us = palabra_data["start_us"]
                # EFECTO ACUMULATIVO: cada palabra dura hasta el fin de su bloque
                duracion = max(ultimo_end - start_us, 1000)
                segmentos_data.append({
                    "text": palabra_data["word"],
                    "start": start_us,
                    "duracion": duracion,
                    "x": x,
                    "y": y,
                })

        # Ordenar por tiempo de inicio para que el greedy sea predecible
        segmentos_data.sort(key=lambda s: s["start"])

        # Distribución greedy: lista de (track_name, [(start, end), ...])
        tracks: List[Tuple[str, List[Tuple[int, int]]]] = []

        color_rgb = self._hex_to_rgb(self.profile.get("text_color", "#FFFFFF"))

        for seg in segmentos_data:
            seg_start = seg["start"]
            seg_end = seg["start"] + seg["duracion"]

            assigned = None
            for idx_t, (tname, intervals) in enumerate(tracks):
                if not self._se_solapa(intervals, seg_start, seg_end):
                    assigned = idx_t
                    break

            if assigned is None:
                track_num = len(tracks) + 1
                tname = f"AUTO_subtitulos_{track_num}"
                self.script.add_track(cc.TrackType.text, tname)
                tracks.append((tname, []))
                assigned = len(tracks) - 1

            tname, intervals = tracks[assigned]

            style = cc.TextStyle(
                size=self.profile.get("text_size", 8.0),
                color=color_rgb,
                align=1,
            )
            clip = cc.ClipSettings(
                transform_x=seg["x"],
                transform_y=seg["y"],
                scale_x=self.profile.get("scale_x", 1.67),
                scale_y=self.profile.get("scale_y", 1.67),
            )
            ts = cc.TextSegment(
                text=seg["text"],
                timerange=cc.Timerange(seg["start"], seg["duracion"]),
                style=style,
                clip_settings=clip,
            )
            self.script.add_segment(ts, tname)
            intervals.append((seg_start, seg_end))

        self._tracks_usados = [tname for tname, _ in tracks]
        return len(segmentos_data)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _se_solapa(self, intervals: List[Tuple[int, int]], new_start: int, new_end: int) -> bool:
        """Devuelve True si (new_start, new_end) se solapa con algún intervalo existente."""
        for s, e in intervals:
            if new_start < e and new_end > s:
                return True
        return False

    def _hex_to_rgb(self, hex_color: str) -> Tuple[float, float, float]:
        """Convierte color hex (#RRGGBB) a tupla (r, g, b) en rango [0, 1]."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)

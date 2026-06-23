import json
import shutil
import os
import threading
from pathlib import Path
from datetime import datetime
from config import PATHS, AUTO_CAPTION_NAMES
from core.logger import logger
from core.exceptions import InvalidDraftError, BackupError
from utils.helpers import detectar_multiplicador_tiempo

class DraftManager:
    PREFIJO_RESIDUAL = "AUTO_"
    MAX_FILE_SIZE_MB = 50

    def __init__(self, draft_path):
        self.json_path = Path(draft_path)
        if not self.json_path.is_file():
            raise FileNotFoundError(f"No es un archivo: {self.json_path}")
        
        file_size_mb = os.path.getsize(self.json_path) / (1024 * 1024)
        if file_size_mb > self.MAX_FILE_SIZE_MB:
            raise ValueError(f"Archivo demasiado grande ({file_size_mb:.1f}MB). Máximo: {self.MAX_FILE_SIZE_MB}MB.")
        
        self.project_folder = self.json_path.parent
        self.backup_path = PATHS["backups"]
        self.data = None

    def load(self):
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except json.JSONDecodeError:
            raise InvalidDraftError("El archivo no es un JSON válido.")
        
        if not isinstance(self.data, dict):
            raise InvalidDraftError("El JSON no tiene la estructura de un draft de CapCut.")
        
        faltantes = []
        if "materials" not in self.data: faltantes.append("materials")
        if "tracks" not in self.data: faltantes.append("tracks")
        if faltantes:
            raise InvalidDraftError(f"Faltan campos obligatorios: {', '.join(faltantes)}")
            
        return self.data

    def create_backup(self):
        self.backup_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_file = self.backup_path / f"{self.json_path.stem}_backup_{timestamp}.json"
        
        try:
            shutil.copy2(self.json_path, backup_file)
            if not backup_file.exists() or backup_file.stat().st_size == 0:
                raise BackupError("El backup se creó pero está vacío.")
        except Exception as e:
            raise BackupError(f"No se pudo crear el backup: {str(e)}")
            
        return backup_file

    def _parse_content(self, content_str):
        if not isinstance(content_str, str): return None
        try: return json.loads(content_str)
        except json.JSONDecodeError: return None

    def _clasificar_material_texto(self, text_mat, mult_tiempo_raiz=1, offset_us=0):
        """Clasifica un material de texto en auto_sin_editar / auto_ya_estilado
        / texto_manual.

        Soporta DOS formatos de CapCut observados con datos reales:
        - Formato viejo: 'words' vive DENTRO de content (JSON string), como
          una lista de dicts {"text":..., "start_time"/"start_us":...} YA EN
          MICROSEGUNDOS y YA ABSOLUTOS respecto al video completo (confirmado
          con los datos reales de "entrv fede baic": start_us=32766666, el
          segundo 32 del video). No necesitan offset ni conversion.
        - Formato nuevo (CapCut 8.8+, confirmado con datos reales de
          "mariaaa baic"): 'words' es un campo SEPARADO a nivel RAIZ del
          material, como arrays paralelos {"start_time":[...], "end_time":
          [...], "text":[...]} en MILISEGUNDOS y RELATIVOS al inicio del
          SEGMENTO (no del video). Confirmado: el segmento de "la dueña..."
          tiene target_timerange.start=1166666us mientras que su words
          empieza en start_time=0 -- sin sumar el offset del segmento, TODAS
          las oraciones del video quedarian con start_us cercano a 0,
          aplastadas una encima de otra. offset_us (target_timerange.start
          del segmento, en microsegundos) se suma DESPUES de aplicar
          mult_tiempo_raiz. mult_tiempo_raiz convierte esos valores crudos a
          microsegundos (ver analyze(), que lo calcula UNA vez para todo el
          draft con utils.helpers.detectar_multiplicador_tiempo).
        """
        try:
            content = self._parse_content(text_mat.get("content"))

            palabras_con_timing = []

            # ── Formato nuevo: words a nivel raiz, arrays paralelos,
            #    RELATIVOS al segmento -> sumar offset_us ────────────────
            words_raiz = text_mat.get("words")
            if isinstance(words_raiz, dict) and words_raiz.get("text"):
                starts = words_raiz.get("start_time", []) or []
                ends = words_raiz.get("end_time", []) or []
                for i, palabra_raw in enumerate(words_raiz.get("text", [])):
                    palabra = (palabra_raw or "").strip()
                    if not palabra:
                        continue
                    start_raw = starts[i] if i < len(starts) else 0
                    end_raw = ends[i] if i < len(ends) else 0
                    palabras_con_timing.append({
                        "word": palabra,
                        "start_us": int(start_raw) * mult_tiempo_raiz + offset_us,
                        "end_us": int(end_raw) * mult_tiempo_raiz + offset_us,
                    })
                if palabras_con_timing:
                    # recognize_task_id poblado = viene de reconocimiento de
                    # voz automatico real (no texto tipeado a mano). Mismo
                    # criterio que ya usa Cleaner.limpiar_autocaption_nativo().
                    if text_mat.get("recognize_task_id"):
                        return "auto_sin_editar", palabras_con_timing
                    return "auto_ya_estilado", palabras_con_timing

            # ── Formato viejo: words dentro de content, lista de dicts,
            #    YA en microsegundos Y YA ABSOLUTOS -- NO sumar offset ──
            if content is not None:
                words = content.get("words", [])
                if words:
                    texto_de_words = "".join(w.get("text", "") for w in words)
                    texts_list = content.get("texts") or []
                    texto_visible = "".join(texts_list) if isinstance(texts_list, list) else ""

                    for w in words:
                        palabra = w.get("text", "").strip()
                        if not palabra:
                            continue

                        start = w.get("start_time")
                        if start is None: start = w.get("start_us", 0)
                        end = w.get("end_time")
                        if end is None: end = w.get("end_us", 0)

                        palabras_con_timing.append({"word": palabra, "start_us": int(start), "end_us": int(end)})

                    if texto_de_words.strip() == texto_visible.strip():
                        return "auto_sin_editar", palabras_con_timing
                    else:
                        return "auto_ya_estilado", palabras_con_timing

            return "texto_manual", None
        except Exception:
            return "texto_manual", None

    def _calcular_multiplicador_raiz(self, texts_list, duration_us: int) -> int:
        """Calcula, para TODO el draft, el multiplicador que convierte los
        timings crudos de 'words' a nivel raiz (formato nuevo de CapCut) a
        microsegundos. Usa la misma heuristica que utils.helpers.
        detectar_multiplicador_tiempo (mediana de duracion de palabra
        ~0.3s), mirando todos los materiales de una sola vez en vez de
        adivinar por separado en cada uno (mas estable con pocas palabras).
        """
        max_raw = 0
        duraciones = []
        for mat in (texts_list or []):
            wd = mat.get("words")
            if not isinstance(wd, dict):
                continue
            starts = wd.get("start_time", []) or []
            ends = wd.get("end_time", []) or []
            for v in ends or starts:
                try:
                    max_raw = max(max_raw, int(v))
                except (TypeError, ValueError):
                    pass
            for a, b in zip(starts, ends):
                try:
                    d = int(b) - int(a)
                    if d > 0:
                        duraciones.append(d)
                except (TypeError, ValueError):
                    pass

        if not duraciones and max_raw == 0:
            return 1  # sin datos del formato nuevo en este draft

        median_dur = 0
        if duraciones:
            duraciones.sort()
            median_dur = duraciones[len(duraciones) // 2]

        return detectar_multiplicador_tiempo(median_dur, max_raw, duration_us)

    def analyze(self):
        if not self.data: self.load()

        materials = self.data.get("materials") or {}
        texts_list = materials.get("texts") or []
        materials_texts = {m["id"]: m for m in texts_list} if isinstance(texts_list, list) else {}
        
        auto_sin_editar = []       
        auto_ya_estilado = []      
        texto_manual = []          
        tracks_residuales_texto = []
        tracks_residuales_audio = []
        materiales_ya_contados = set()
        
        total_segmentos_texto = 0
        total_segmentos_audio = 0

        # Calcular UNA vez para todo el draft el multiplicador que convierte
        # los timings crudos del formato nuevo (words a nivel raiz) a
        # microsegundos. Mismo criterio que utils.extract_autocaption usa
        # para el camino de respaldo (duracion tipica de palabra ~0.3s).
        duration_us = int(self.data.get("duration", 0) or 0)
        mult_tiempo_raiz = self._calcular_multiplicador_raiz(texts_list, duration_us)

        tracks_list = self.data.get("tracks") or []
        for track in tracks_list:
            track_name = track.get("name", "") or ""
            track_type = track.get("type", "") or ""
            
            if track_name.startswith(self.PREFIJO_RESIDUAL):
                if track_type == "text": tracks_residuales_texto.append(track_name)
                elif track_type == "audio": tracks_residuales_audio.append(track_name)
            
            segmentos = track.get("segments", []) or []
            if track_type == "text": total_segmentos_texto += len(segmentos)
            elif track_type == "audio": total_segmentos_audio += len(segmentos)
            
            es_track_autocaption = track_name in AUTO_CAPTION_NAMES
            # OJO: antes, cualquier track con name="" (formato nuevo de
            # CapCut 8.8+, confirmado con datos reales: el track de
            # auto-caption recien generado tiene name vacio) se trataba como
            # "manual" SOLO por el nombre, sin mirar el contenido real -> se
            # descartaba de entrada con auto_ya_estilado.append([]) antes de
            # llegar a _clasificar_material_texto. Ahora un track sin nombre
            # NO se asume manual; se deja que _clasificar_material_texto
            # decida por el contenido real de cada material (usa
            # recognize_task_id, que es la marca real de reconocimiento de
            # voz automatico, igual que Cleaner.limpiar_autocaption_nativo()).
            es_track_con_nombre_manual = (
                bool(track_name)
                and not es_track_autocaption
                and not track_name.startswith(self.PREFIJO_RESIDUAL)
            )
            
            if track_type == "text":
                for seg in segmentos:
                    mat_id = seg.get("material_id")
                    if mat_id in materiales_ya_contados: continue 
                    
                    text_mat = materials_texts.get(mat_id)
                    if not text_mat: continue
                    
                    materiales_ya_contados.add(mat_id)
                    
                    if es_track_con_nombre_manual:
                        auto_ya_estilado.append([])
                        continue
                    
                    categoria, palabras = self._clasificar_material_texto(
                        text_mat,
                        mult_tiempo_raiz,
                        offset_us=int((seg.get("target_timerange") or {}).get("start", 0) or 0),
                    )
                    if categoria == "auto_sin_editar" and palabras:
                        auto_sin_editar.append(palabras)
                    elif categoria == "auto_ya_estilado":
                        auto_ya_estilado.append(palabras or [])
                    elif categoria == "texto_manual":
                        content = self._parse_content(text_mat.get("content"))
                        if content and isinstance(content.get("content"), str):
                            texto_manual.append(content["content"])
                        elif content and isinstance(content.get("texts"), list):
                            texto_manual.append("".join(content.get("texts") or []))
                        else:
                            texto_manual.append(text_mat.get("content", "")[:50] + "...")

        # duration_us ya se calculo arriba (linea 163) para detectar el
        # multiplicador de tiempo del formato nuevo.
        return {
            "oraciones_auto_sin_editar": auto_sin_editar,
            "cantidad_oraciones_procesables": len(auto_sin_editar),
            "cantidad_palabras_procesables": sum(len(o) for o in auto_sin_editar),
            "cantidad_oraciones_ya_estiladas": len(auto_ya_estilado),
            "cantidad_textos_manuales": len(texto_manual),
            "tracks_residuales_texto": tracks_residuales_texto,
            "tracks_residuales_audio": tracks_residuales_audio,
            "duracion_video_seg": duration_us / 1_000_000 if duration_us else 0,
            "total_segmentos_texto": total_segmentos_texto,
            "total_segmentos_audio": total_segmentos_audio,
        }

    @classmethod
    def oraciones_desde_json(cls, json_path):
        """Atajo: devuelve solo las oraciones de auto-caption SIN editar.

        Returns:
            (oraciones, stats) con oraciones = List[List[{word,start_us,end_us}]]
        """
        mgr = cls(json_path)
        result = mgr.analyze()
        oraciones = result["oraciones_auto_sin_editar"]
        stats = {
            "oraciones": result["cantidad_oraciones_procesables"],
            "palabras": result["cantidad_palabras_procesables"],
            "duracion_seg": result["duracion_video_seg"],
        }
        return oraciones, stats

    def analyze_async(self, callback):
        """Analiza en thread separado para no bloquear UI. callback(error, result)"""
        thread = threading.Thread(target=self._analyze_threaded, args=(callback,), daemon=True)
        thread.start()
    
    def _analyze_threaded(self, callback):
        try:
            self.load()
            backup = self.create_backup()
            result = self.analyze()
            result['backup_name'] = backup.name
            callback(None, result)
        except Exception as e:
            logger.error(f"Error en análisis asíncrono: {e}")
            callback(e, None)
import json
import shutil
import os
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from config import PATHS, AUTO_CAPTION_NAMES
from core.logger import logger
from core.exceptions import InvalidDraftError, BackupError, AnalysisError

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

    def _clasificar_material_texto(self, text_mat):
        try:
            content = self._parse_content(text_mat.get("content"))
            if content is None: return "texto_manual", None
            
            words = content.get("words", [])
            if not words: return "texto_manual", None
            
            texto_de_words = "".join(w.get("text", "") for w in words)
            texts_list = content.get("texts") or []
            texto_visible = "".join(texts_list) if isinstance(texts_list, list) else ""
            
            palabras_con_timing = []
            for w in words:
                palabra = w.get("text", "").strip()
                if not palabra: continue
                
                start = w.get("start_time")
                if start is None: start = w.get("start_us", 0)
                end = w.get("end_time")
                if end is None: end = w.get("end_us", 0)
                
                palabras_con_timing.append({"word": palabra, "start_us": int(start), "end_us": int(end)})
            
            if texto_de_words.strip() == texto_visible.strip():
                return "auto_sin_editar", palabras_con_timing
            else:
                return "auto_ya_estilado", palabras_con_timing
        except Exception:
            return "texto_manual", None

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
            es_track_manual = (not es_track_autocaption) and (not track_name.startswith(self.PREFIJO_RESIDUAL))
            
            if track_type == "text":
                for seg in segmentos:
                    mat_id = seg.get("material_id")
                    if mat_id in materiales_ya_contados: continue 
                    
                    text_mat = materials_texts.get(mat_id)
                    if not text_mat: continue
                    
                    materiales_ya_contados.add(mat_id)
                    
                    if es_track_manual:
                        auto_ya_estilado.append([])
                        continue
                    
                    categoria, palabras = self._clasificar_material_texto(text_mat)
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

        duration_us = self.data.get("duration", 0) or 0
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
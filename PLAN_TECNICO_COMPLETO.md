# 🏗️ Plan Técnico COMPLETO: Sistema CapCut Auto-Subtitle (v2.1)

## 🎯 Objetivo Final

Automatizar **dos tareas críticas** que antes se hacían manualmente en CapCut:

1. **✅ Karaoke acumulativo palabra por palabra**
   - Tomar auto-caption nativo (líneas sin estilo)
   - Convertir a subtítulos donde cada palabra aparece y **permanece visible** hasta fin de oración/bloque
   - Patrón visual: zigzag centrado sutil (±0.20), anti-colisión real, no solapamientos

2. **✅ Clicks de audio sincronizados**
   - Inserciones de audio en 2 momentos de cada oración (primera y última palabra)
   - Sincronización exacta con timestamps de CapCut
   - Control de volumen y track separado

---

## 📐 Criterios de Diseño VALIDADOS (NO cambiar)

| Criterio | Especificación | Por qué |
|----------|---|---|
| **Ancho de columna** | ±0.20 (NO ±0.35 ni ±0.55) | Usuario lo probó, es el equilibrio justo |
| **Karaoke acumulativo** | Palabra aparece + se queda hasta fin bloque | Efecto visual deseado |
| **Espaciado variable** | Cortas (1-3 letras): 0.05px, Largas (8+): 0.10px | Densidad visual consistente |
| **Palabras largas** | Se acercan 50% al centro | Evita corte de bordes |
| **División inteligente** | Max 5 palabras/bloque, corta en pausas ≥60ms | Límite geométrico + habla natural |
| **Overlap real** | Umbral ≥150ms para detectar diálogo | Reduce falsos positivos (ruido de transcripción) |
| **Clicks por oración** | Exactamente 2 (primera + última) | Suena bien, no excesivo |
| **Formato** | Palabra por palabra individual (NO párrafo en caja única) | Usuario lo rechazó explícitamente |

---

## 📊 Diagnóstico del Repo Actual

### ✅ Ya Funciona Bien
- `DraftManager`: clasificación, backup, async ✓
- `step1_project.py`: UI limpia para seleccionar proyecto ✓
- Estructura modular core/ui/utils/config ✓
- `default_profile.json`: sistema de perfiles ✓

### ❌ Está Vacío o Mal
| Módulo | Problema | Impacto |
|--------|----------|--------|
| `SubtitleEngine` | Solo `pass` | **BLOQUEADOR**: Sin generación de subtítulos |
| `ClickEngine` | Lista vacía | **BLOQUEADOR**: Sin generación de clicks |
| `step2_style.py` | Mezcla PyQt5 + CustomTkinter | Inconsistente, difícil de mantener |
| `step3_audio.py` | Solo clase vacía `AudioSettings` | **BLOQUEADOR**: Sin UI de clicks |
| `step4_execute.py` | Solo `print` | **BLOQUEADOR**: No ejecuta pipeline |
| `Cleaner` | Muy básico | No limpia tracks de CapCut reales |

---

## 🏗️ Arquitectura Mejorada

### Cambios Clave vs Plan Original

**1. Menos módulos pequeños, más lógica centralizada**
```
Antes (9 módulos micro):  collision_system, overlap_detector, block_splitter, 
                          position_calculator, style_injector, etc.

Ahora (3 módulos smart): 
  - subtitle_engine.py (centraliza todo: split, overlap, collision, position)
  - click_engine.py (timestamps + audio insert)
  - style_injector.py (inyección de estilos, mantiene separado)
```
Razón: Más fácil de debuggear, menos acoplamiento, más rápido de testear.

**2. Servicios orquestadores**
```
services/
  ├── draft_service.py       ← Orquesta el pipeline completo
  ├── validation_service.py  ← Valida datos ANTES de ejecutar
  └── preview_service.py     ← Genera vista previa en JSON
```

**3. Utils más inteligentes**
```
utils/
  ├── timing.py              ← Conversiones microsegundos ↔ ms
  ├── geometry.py            ← Cálculos de colisión (simple!)
  └── capcut_config.py       ← Detección de rutas CapCut
```

---

## 🔧 Módulos Detallados (Mejorados)

### 1. `core/subtitle_engine.py` - **CENTRALIZADO**

**Cambio crítico**: Unificar lógica de split, overlap, collision, posición.

```python
class SubtitleEngine:
    """Motor central de generación de subtítulos.
    
    Integra:
    - División de oraciones largas (≤5 palabras)
    - Detección de overlap real (≥150ms)
    - Cálculo de posiciones con anti-colisión
    - Inyección de estilos CapCut
    """
    
    # Constantes validadas por usuario
    MAX_PALABRAS_POR_BLOQUE = 5
    PAUSA_MINIMA_SPLIT_US = 60_000      # 60ms
    UMBRAL_OVERLAP_REAL_US = 150_000    # 150ms
    ANCLA_IZQUIERDA = -0.20
    ANCLA_DERECHA = 0.20
    ANCHO_POR_CARACTER = 0.15
    PASO_Y_CORTO = 0.05
    PASO_Y_LARGO = 0.10
    
    def __init__(self, draft_folder: str, draft_name: str, profile: dict):
        """Inicializa con draft de CapCut."""
        self.draft_folder = cc.DraftFolder(draft_folder)
        # ⚠️ CRÍTICO: load_template, NO duplicate_as_template
        self.script = self.draft_folder.load_template(draft_name)
        self.profile = profile
    
    def generate(self, oraciones_auto: List[List[dict]]) -> dict:
        """Pipeline completo: divide → detecta overlap → calcula posiciones → inserta."""
        
        # 1. Detectar diálogo simultáneo (≥150ms overlap)
        pares_overlap = self._detectar_overlap_real(oraciones_auto)
        
        # 2. Dividir oraciones largas en bloques ≤5 palabras
        bloques = self._dividir_en_bloques(oraciones_auto, pares_overlap)
        
        # 3. Calcular posiciones (X, Y) con anti-colisión
        posiciones = self._calcular_posiciones(bloques, pares_overlap)
        
        # 4. Crear segmentos en CapCut
        total_palabras = self._crear_segmentos(bloques, posiciones, pares_overlap)
        
        # 5. Guardar
        self.script.save()
        
        return {
            "success": True,
            "total_palabras": total_palabras,
            "total_bloques": len(bloques),
            "pares_overlap": len(pares_overlap),
            "track_name": "AUTO_subtitulos"
        }
    
    def _detectar_overlap_real(self, oraciones: List[List[dict]]) -> List[tuple]:
        """Detecta solo overlaps reales (≥150ms)."""
        pares = []
        for i in range(len(oraciones) - 1):
            fin_i = max(p["end_us"] for p in oraciones[i])
            inicio_j = min(p["start_us"] for p in oraciones[i + 1])
            overlap = fin_i - inicio_j
            
            # Solo overlap real
            if overlap >= self.UMBRAL_OVERLAP_REAL_US:
                pares.append((i, i + 1))
        
        return pares
    
    def _dividir_en_bloques(self, oraciones: List[List[dict]], pares_overlap: List[tuple]) -> List[dict]:
        """Divide oraciones largas en bloques ≤5 palabras, cortando en pausas naturales."""
        bloques = []
        
        for idx_or, oracion in enumerate(oraciones):
            if len(oracion) <= self.MAX_PALABRAS_POR_BLOQUE:
                # Pequeña, agregar tal cual
                bloques.append({
                    "idx_oracion": idx_or,
                    "palabras": oracion,
                    "es_overlap": any(idx_or in par for par in pares_overlap)
                })
            else:
                # Grande, dividir en bloques
                bloques_or = self._dividir_oracion(oracion, idx_or)
                bloques.extend(bloques_or)
        
        return bloques
    
    def _dividir_oracion(self, oracion: List[dict], idx: int) -> List[dict]:
        """Divide una oración en bloques ≤5, priorizando pausas naturales."""
        bloques = []
        inicio = 0
        
        while inicio < len(oracion):
            # Tomar máximo 5 palabras
            fin = min(inicio + self.MAX_PALABRAS_POR_BLOQUE, len(oracion))
            
            # Si no es el final, buscar pausa para cortar
            if fin < len(oracion):
                pausa_idx = self._buscar_pausa_para_corte(oracion, inicio, fin)
                if pausa_idx is not None:
                    fin = pausa_idx + 1
            
            bloque_palabras = oracion[inicio:fin]
            bloques.append({
                "idx_oracion": idx,
                "palabras": bloque_palabras,
                "es_overlap": False  # Actualizará el caller
            })
            
            inicio = fin
        
        return bloques
    
    def _buscar_pausa_para_corte(self, oracion: List[dict], inicio: int, fin: int) -> Optional[int]:
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
    
    def _calcular_posiciones(self, bloques: List[dict], pares_overlap: List[tuple]) -> dict:
        """Calcula (X, Y) de cada palabra con anti-colisión."""
        posiciones = {}  # palabra_id → (x, y)
        
        for bloque in bloques:
            # Determinar zona Y según overlap
            es_overlap_segundo = any(
                bloque["idx_oracion"] == par[1] for par in pares_overlap
            )
            
            if bloque["es_overlap"]:
                y_zona_min, y_zona_max = (-0.4, -0.05) if es_overlap_segundo else (0.05, 0.4)
            else:
                y_zona_min, y_zona_max = -0.4, 0.4
            
            # Limpiar cajas ocupadas para este bloque
            cajas_ocupadas = []
            y_actual = y_zona_min + 0.05
            
            # Calcular posición de cada palabra
            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra = palabra_data["word"]
                ancho_palabra = len(palabra) * self.ANCHO_POR_CARACTER
                
                # Zigzag: alternar izquierda/derecha
                x = self.ANCLA_IZQUIERDA if i % 2 == 0 else self.ANCLA_DERECHA
                
                # Palabras largas se acercan 50% al centro
                if len(palabra) >= 8:
                    x *= 0.5
                
                # Clamp para no salir de pantalla
                x = max(-0.45 + ancho_palabra/2, min(0.45 - ancho_palabra/2, x))
                
                # Anti-colisión simple: si choca, mover arriba
                intento = 0
                while intento < 5:
                    choca = False
                    for (cx, cy, cw) in cajas_ocupadas:
                        if abs(x - cx) < (ancho_palabra + cw) / 2 and abs(y_actual - cy) < 0.08:
                            choca = True
                            break
                    
                    if not choca:
                        break
                    
                    y_actual += 0.05
                    intento += 1
                
                # Guardar posición
                palabra_id = f"{bloque['idx_oracion']}_{i}"
                posiciones[palabra_id] = (x, y_actual)
                cajas_ocupadas.append((x, y_actual, ancho_palabra))
                
                # Paso Y variable según largo de palabra
                paso = self.PASO_Y_CORTO if len(palabra) <= 3 else self.PASO_Y_LARGO
                y_actual += paso
                y_actual = min(y_actual, y_zona_max - 0.05)
        
        return posiciones
    
    def _crear_segmentos(self, bloques: List[dict], posiciones: dict, pares_overlap: List[tuple]) -> int:
        """Crea TextSegment en CapCut para cada palabra."""
        track_name = "AUTO_subtitulos"
        total_palabras = 0
        
        for bloque in bloques:
            for i, palabra_data in enumerate(bloque["palabras"]):
                palabra_id = f"{bloque['idx_oracion']}_{i}"
                x, y = posiciones.get(palabra_id, (0, 0))
                
                # Crear material de texto
                material = cc.TextMaterial(
                    text=palabra_data["word"],
                    font_path=self.profile.get("font_path"),
                    text_size=self.profile.get("text_size", 30),
                    text_color=self.profile.get("text_color", "#FFFFFF"),
                )
                
                # Inyectar estilos críticos
                material.type = "subtitle"  # NO "text"
                material.alignment = 1  # Centrado
                
                # Sombras a nivel raíz
                if self.profile.get("shadow_enabled", True):
                    material.has_shadow = True
                    material.shadow_color = self.profile.get("shadow_color", "#000000")
                    material.shadow_alpha = self.profile.get("shadow_alpha", 0.33)
                    material.shadow_distance = self.profile.get("shadow_distance", 17.0)
                    material.shadow_angle = self.profile.get("shadow_angle", -115.9)
                
                self.script.add_material(material)
                
                # Crear segmento
                start_us = palabra_data["start_us"]
                end_us = palabra_data["end_us"]
                
                # Extender duración para efecto acumulativo
                if i < len(bloque["palabras"]) - 1:
                    end_us = bloque["palabras"][i + 1]["start_us"]
                
                duracion = max(end_us - start_us, 1000)  # Mínimo 1ms
                
                segmento = cc.TextSegment(
                    material,
                    cc.Timerange(start_us, duracion)
                )
                
                # Posición
                segmento.clip.transform.x = x
                segmento.clip.transform.y = y
                segmento.clip.scale.x = self.profile.get("scale_x", 1.67)
                segmento.clip.scale.y = self.profile.get("scale_y", 1.67)
                
                self.script.add_segment(segmento, track_name)
                total_palabras += 1
        
        return total_palabras
```

---

### 2. `core/click_engine.py` - **Simplificado y Funcional**

```python
class ClickEngine:
    """Motor de clicks de audio sincronizados."""
    
    TRACK_NAME = "AUTO_clicks"
    VOLUMEN_DEFAULT = 0.4
    MODO_DEFAULT = "2_por_oracion"  # primera + última
    
    def __init__(self, script, ruta_sonido: str):
        self.script = script
        self.ruta_sonido = ruta_sonido
        self.material_audio = None
    
    def generate(self, oraciones: List[List[dict]], modo: str = None) -> dict:
        """Genera clicks en momentos específicos."""
        modo = modo or self.MODO_DEFAULT
        
        if not os.path.exists(self.ruta_sonido):
            raise FileNotFoundError(f"Sonido no encontrado: {self.ruta_sonido}")
        
        # ⚠️ CRÍTICO: Crear material Y registrarlo explícitamente
        self.material_audio = cc.AudioMaterial(
            self.ruta_sonido,
            material_name="click_subtitulo"
        )
        self.script.add_material(self.material_audio)
        
        # Calcular timestamps según modo
        timestamps = self._calcular_timestamps(oraciones, modo)
        
        # Crear track
        self._asegurar_track()
        
        # Insertar clicks
        for ts in timestamps:
            segmento = cc.AudioSegment(
                self.material_audio,
                cc.Timerange(ts, int(self.material_audio.duration))
            )
            segmento.volume = self.VOLUMEN_DEFAULT
            self.script.add_segment(segmento, self.TRACK_NAME)
        
        self.script.save()
        
        return {
            "success": True,
            "total_clicks": len(timestamps),
            "track_name": self.TRACK_NAME
        }
    
    def _calcular_timestamps(self, oraciones: List[List[dict]], modo: str) -> List[int]:
        """Calcula timestamps donde insertar clicks."""
        timestamps = set()
        
        for oracion in oraciones:
            n = len(oracion)
            
            if modo == "2_por_oracion":
                indices = [0, n - 1]  # Primera y última
            else:
                indices = [0, n // 2, n - 1]  # Primera, medio, última
            
            for idx in indices:
                if 0 <= idx < n:
                    timestamps.add(oracion[idx]["start_us"])
        
        return sorted(timestamps)
    
    def _asegurar_track(self) -> None:
        """Crea track si no existe."""
        for track in self.script.imported_tracks:
            if track.name == self.TRACK_NAME:
                return  # Ya existe
        
        self.script.add_track(cc.TrackType.audio, self.TRACK_NAME)
```

---

### 3. `services/draft_service.py` - **Orquestador del Pipeline**

```python
class DraftService:
    """Orquesta el pipeline completo de generación."""
    
    def __init__(self, draft_folder: str, profile: dict):
        self.draft_folder = draft_folder
        self.profile = profile
    
    def generar_completo(self, draft_name: str, oraciones_auto: List[List[dict]], 
                         sonido_clicks: str = None) -> dict:
        """Pipeline: limpia → genera subtítulos → genera clicks."""
        
        try:
            # 1. Cargar draft
            script = cc.DraftFolder(self.draft_folder).load_template(draft_name)
            
            # 2. Limpiar tracks viejos (CRÍTICO)
            cleaner = Cleaner(script)
            tracks_limpiados_texto = cleaner.limpiar_tracks_texto()
            tracks_limpiados_audio = cleaner.limpiar_tracks_audio()
            
            # 3. Generar subtítulos
            subtitle_engine = SubtitleEngine(self.draft_folder, draft_name, self.profile)
            resultado_subtitulos = subtitle_engine.generate(oraciones_auto)
            
            # 4. Generar clicks (opcional)
            resultado_clicks = None
            if sonido_clicks:
                click_engine = ClickEngine(script, sonido_clicks)
                resultado_clicks = click_engine.generate(oraciones_auto)
            
            return {
                "success": True,
                "draft_name": draft_name,
                "tracks_limpiados_texto": tracks_limpiados_texto,
                "tracks_limpiados_audio": tracks_limpiados_audio,
                "subtitulos": resultado_subtitulos,
                "clicks": resultado_clicks
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "draft_name": draft_name
            }
```

---

## 📝 Configuración Actualizada (`config/settings.json`)

```json
{
  "app_name": "CapCut Auto-Subtitle System v2.1",
  "version": "2.1.0",
  "capcut": {
    "default_projects_path": "C:\\Users\\{USER}\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft",
    "auto_caption_track_names": [
      "auto_caption",
      "Reconocimiento de voz",
      "Auto captions"
    ]
  },
  "subtitle_style": {
    "font_path": "",
    "text_size": 30,
    "text_color": "#FFFFFF",
    "scale_x": 1.67,
    "scale_y": 1.67,
    "alignment": 1,
    "type": "subtitle",
    "shadow_enabled": true,
    "shadow_color": "#000000",
    "shadow_alpha": 0.33,
    "shadow_angle": -115.9,
    "shadow_distance": 17.0
  },
  "layout": {
    "ancla_izquierda": -0.20,
    "ancla_derecha": 0.20,
    "ancho_por_caracter": 0.15,
    "paso_y_corto": 0.05,
    "paso_y_largo": 0.10,
    "max_palabras_por_bloque": 5,
    "limite_y_arriba": -0.4,
    "limite_y_abajo": 0.4
  },
  "overlap_detection": {
    "umbral_overlap_real_us": 150000,
    "pausa_minima_split_us": 60000
  },
  "clicks": {
    "modo_default": "2_por_oracion",
    "volumen": 0.4,
    "nombre_track": "AUTO_clicks"
  },
  "safety": {
    "siempre_cerrar_capcut": true,
    "crear_backup_antes": true,
    "limpiar_tracks_antes": true,
    "validar_datos_antes": true
  }
}
```

---

## 🚀 Plan de Implementación (Realista)

### **Fase 1: Core Engines (3-4 días)**
- [x] Reescribir `SubtitleEngine` centralizado
- [x] Reescribir `ClickEngine` con `add_material` explícito
- [x] Crear `DraftService` orquestador
- [ ] Tests unitarios para cada uno
- [ ] Validar con videos "tiggo 4" y "arrizzo 8"

### **Fase 2: UI Step-by-Step (2-3 días)**
- [ ] Reescribir `step2_style.py` en CustomTkinter (selector de fuente, color, escala)
- [ ] Reescribir `step3_audio.py` con UI de clicks
- [ ] Reescribir `step4_execute.py` con pipeline + barra de progreso
- [ ] Agregar preview visual de posiciones

### **Fase 3: Integración + Pulido (2-3 días)**
- [ ] Detección automática de rutas CapCut
- [ ] Sistema de perfiles guardables
- [ ] Manejo de errores robusto
- [ ] Documentación completa
- [ ] Tests de integración end-to-end

---

## ❌ Errores del Handoff - CHECKLIST RESUELTO

| # | Error | Solución |
|---|-------|---------|
| 1 | `KeyError: 'fps'` | Usar `load_template()` en `SubtitleEngine.__init__` |
| 2 | Auto-caption se pierde | Extraer antes de modificar, guardar en backup |
| 3 | Texto duplicado | `Cleaner` corre ANTES de generar |
| 4 | Texto chico | `text_size` + `scale_x/y` + `type: "subtitle"` + sombras raíz |
| 5 | Palabras cortadas | Anclas ±0.20 + clamp en `_calcular_posiciones` |
| 6 | Solapamiento | Anti-colisión simple en loop |
| 7 | Oraciones largas | Split en bloques ≤5 en pausas ≥60ms |
| 8 | Formato párrafo rechazado | Documentación: **NO usar `auto_wrapping=True`** |
| 9 | Overlap falso | Umbral ≥150ms en `_detectar_overlap_real` |
| 10 | Última palabra choca | Duración extendida hasta inicio de siguiente palabra |
| 11 | Bloques pegados | Zona Y centrada en `_calcular_posiciones` |
| 12 | Track audio no aparece | `script.add_material(audio_material)` **EXPLÍCITO** |
| 13 | Demasiados clicks | Modo `2_por_oracion` por defecto |

---

## ✅ Próximos Pasos Inmediatos

**Prioridad 1**: Implementar `SubtitleEngine` centralizado (la lógica más crítica)

**Prioridad 2**: Tests unitarios para `_detectar_overlap_real`, `_dividir_en_bloques`, `_calcular_posiciones`

**Prioridad 3**: Integración con UI existente en `step1_project.py`

¿Comenzamos?

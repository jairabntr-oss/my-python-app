# Análisis del Formato de Estilo - CapCut Automation

## Parámetros Reales Extraídos de los Drafts

Basado en análisis de los drafts **"tiggo 4"** y **"arrizzo 8"** (junio 2026).

### 1. Escala del Clip
- **tiggo 4**: ~1.67 (167%) consistente en todos los bloques
- **arrizzo 8**: variable de 1.0 a 1.84, promedio ~1.5
- **Recomendación**: usar 1.67 como valor estándar

### 2. Fuente
- **Nombre**: Poppins-Bold
- **Font ID**: 7312373689708712449
- **Path**: `C:\Users\user2\AppData\Local\CapCut\User Data\Cache\effect\7312373689708712449\d090413fb1d5672cdf7177fea62fbccd\Poppins-Bold.ttf`
- **Tamaño base**: 30px

### 3. Color y Sombra
- **Color del texto**: #FFFFFF (blanco)
- **Sombra habilitada**: sí
- **Color sombra**: #000000 (negro)
- **Alpha sombra**: 0.33 (33%)
- **Distancia sombra**: 17.0px
- **Ángulo sombra**: -115.9°

### 4. Posicionamiento X (Zigzag Centrado)
- **Ancla izquierda**: -0.25
- **Ancla derecha**: +0.25
- **Ancho por carácter**: 0.15

El patrón zigzag alterna las palabras entre izquierda y derecha, con reduc
ciones para palabras largas (8+ letras) para evitar que se corten.

### 5. Posicionamiento Y (Separación Vertical)
- **Paso Y corto** (1-3 letras): 0.05
- **Paso Y medio** (4-7 letras): 0.08
- **Paso Y largo** (8+ letras): 0.10
- **Límite Y superior**: -0.70 (para evitar corte)
- **Límite Y inferior**: 0.70 (para evitar corte)

### 6. División de Oraciones
- **Máximo de palabras por bloque**: 5
- **Detecta pausas naturales**: gaps >= 60ms

### 7. Diálogo Simultáneo
- **Umbral de overlap real**: 150ms (150_000 microsegundos)
- **Posición para overlap**: mitad superior (-0.35) y mitad inferior (+0.35)

## Cómo Usar Esta Configuración

1. Estos parámetros se guardan automáticamente en `config/user_profile.json`
2. El `LearningEngine` los carga y puede modificarlos según nuevos edits
3. El `CapcutEngine` usa estos valores para generar subtítulos automáticos
4. Se pueden exportar/importar entre proyectos con `export_settings()` e `import_settings()`

## Próximos Pasos

- [ ] Validar con videos "tiggo 4" y "arrizzo 8" reales
- [ ] Ajustar `char_width` si hay solapamientos
- [ ] Calibrar `step_y_*` según densidad de captions
- [ ] Crear herramienta de vista previa en la UI

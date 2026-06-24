# My Python App

## Descripción
Herramienta de automatización para generar subtítulos estilo **karaoke acumulativo** en proyectos de CapCut. Aprende tus patrones de edición y los aplica automáticamente usando la API `pycapcut`.

Incluye:
- Motor de subtítulos karaoke con zigzag y anti-colisión de palabras.
- Motor de clicks de audio sincronizados por oración.
- Interfaz gráfica con `customtkinter` (pasos: Proyecto → Estilo → Clicks → Generar).
- Motor de aprendizaje de estilos y configuraciones personales.

## Estructura del proyecto
```
my-python-app/
├── config/
│   ├── __init__.py          # Constantes centrales (colores, rutas, nombres de tracks)
│   ├── default_profile.json
│   └── settings.json
├── core/
│   ├── capcut_engine.py     # Integración con pycapcut
│   ├── cleaner.py           # Limpieza de tracks residuales
│   ├── click_engine.py      # Generación de clicks de audio
│   ├── draft_manager.py     # Análisis y backup de drafts
│   ├── exceptions.py        # Excepciones personalizadas
│   ├── learning_engine.py   # Perfil de estilos del usuario
│   ├── logger.py            # Configuración de logging
│   └── subtitle_engine.py   # Pipeline de subtítulos karaoke
├── services/
│   └── draft_service.py     # Orquestador del pipeline completo
├── tests/
│   ├── test_draft_manager.py
│   └── test_subtitle_engine.py
├── ui/
│   ├── components/buttons.py
│   ├── main_window.py
│   ├── step1_project.py
│   ├── step2_style.py
│   ├── step3_audio.py
│   └── step4_execute.py
├── utils/
│   ├── capcut_parser.py     # Parseo de draft_content.json
│   ├── extract_autocaption.py
│   └── helpers.py
├── app.py                   # Punto de entrada de la UI
├── generar_subtitulos_baic_v5.py  # Script de línea de comandos
├── pyproject.toml
└── requirements.txt
```

## Instalación

```bash
# 1. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate       # Linux / macOS
.venv\Scripts\activate          # Windows

# 2. Instalar dependencias de producción
pip install -r requirements.txt

# 3. (Opcional) Instalar dependencias de desarrollo
pip install -e ".[dev]"
```

## Uso — Procesar un video nuevo (flujo recomendado)

Todo el flujo se hace desde la interfaz gráfica, sin necesidad de correr
scripts a mano ni saber qué hace cada uno.

```bash
python app.py
```

Pasos dentro de la app:

1. **Paso 1 — Proyecto.** La app lista automáticamente tus proyectos de
   CapCut (el más reciente arriba). Elegí uno del desplegable y presioná
   **Analizar**.
   - Si el proyecto **no tiene subtítulos automáticos todavía**, la app te
     dice exactamente qué hacer (generar los Subtítulos automáticos en
     CapCut, guardar, cerrar CapCut y volver a analizar).
   - El botón **🔍 Diagnosticar** muestra un reporte detallado del estado
     interno del proyecto si algo no cuadra.
2. **Paso 2 — Estilo.** Confirmá o ajustá el estilo visual.
3. **Paso 3 — Clicks (opcional).** Activá sonidos de click si los querés.
4. **Paso 4 — Generar.** Antes de generar, la app **verifica que CapCut
   esté cerrado** (si está abierto, te avisa, porque al cerrarse
   sobreescribiría el resultado). Presioná **Generar** y listo.

> ⚠️ **Regla de oro:** CapCut tiene que estar **cerrado** mientras se
> genera. La app lo verifica, pero conviene cerrarlo vos también desde el
> Administrador de Tareas si tenés dudas.

### Diagnóstico por línea de comandos (opcional)

Si querés inspeccionar un draft sin abrir la UI:

```bash
python -m utils.diagnostico "C:\ruta\al\draft_content.json"
```

### Scripts de línea de comandos (avanzado / legacy)

Los scripts sueltos (`generar_subtitulos_baic_v5.py`, etc.) siguen
existiendo para casos puntuales, pero el flujo recomendado es la UI.

## Ejecutar pruebas
```bash
pytest -q
```

## Lint y formato
```bash
ruff check .
black .
mypy .
```

## Configuración de usuario
Edita `config/user_profile.json` para ajustar:
- **Fuente, tamaño y color** del texto.
- **Escala y posicionamiento** (zigzag, anclas).
- **Ruta de drafts** de CapCut en tu sistema.

> ⚠️ **Escala unificada:** el valor `scale` debe coincidir en `config/settings.json`,
> `config/user_profile.json` y el default de `LearningEngine`. Actualmente está en
> **3.037 (~303%)**, la calibración validada del proyecto original. Si tu estilo
> manual usa otra escala, cambiala en los tres lugares (ver
> `ANALISIS_FORMATO_ESTILO.md`).

## Dos formas de generar (mismo resultado)
- **UI** (`app.py`) y **test de integración**: usan `DraftService` +
  `SubtitleEngine`, leyendo el perfil de `settings.json`.
- **CLI** (`generar_subtitulos_baic_v5.py`): usa `CapcutEngine` +
  `LearningEngine`, leyendo `user_profile.json`.

Ambas rutas comparten el mismo parser (`AutocaptionExtractor`) y el mismo
motor de posicionamiento, por lo que producen subtítulos equivalentes.

## Contributing
Las contribuciones son bienvenidas. Por favor abre un issue o envía un pull request.

## Licencia
MIT License. Ver el archivo `LICENSE` para más detalles.

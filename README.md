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

## Uso

### Interfaz gráfica
```bash
python app.py
```

### Script de línea de comandos
```bash
python generar_subtitulos_baic_v5.py
```
Selecciona el proyecto interactivamente y confirma para generar.

### Test de integración (dry-run)
```bash
python test_integration_real.py "C:\ruta\al\draft_content.json" "nombre_del_draft"
```

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

## Contributing
Las contribuciones son bienvenidas. Por favor abre un issue o envía un pull request.

## Licencia
MIT License. Ver el archivo `LICENSE` para más detalles.

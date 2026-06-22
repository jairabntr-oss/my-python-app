import json
import uuid
from typing import Any

try:
    from jsonschema import validate, ValidationError
    _JSONSCHEMA_AVAILABLE = True
except ImportError:
    _JSONSCHEMA_AVAILABLE = False


def read_json_file(file_path: str) -> Any:
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def write_json_file(file_path: str, data: Any) -> None:
    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def validate_json_schema(data: Any, schema: dict) -> bool:
    if not _JSONSCHEMA_AVAILABLE:
        raise ImportError("jsonschema no está instalado. Ejecuta: pip install jsonschema")
    try:
        validate(instance=data, schema=schema)
        return True
    except ValidationError:
        return False

def flatten_list(nested_list: list[list]) -> list:
    return [item for sublist in nested_list for item in sublist]

def generate_unique_id(existing_ids: set[str]) -> str:
    new_id = str(uuid.uuid4())
    while new_id in existing_ids:
        new_id = str(uuid.uuid4())
    return new_id


def detectar_multiplicador_tiempo(median_dur_raw: int, max_raw: int, duration_us: int) -> int:
    """Factor para llevar timings crudos de palabras al estandar de
    microsegundos del proyecto.

    Vive en helpers.py (modulo neutral, sin dependencias de core/) porque
    tanto core/draft_manager.py como utils/extract_autocaption.py la
    necesitan, y draft_manager <-> extract_autocaption tienen un import
    circular si una depende de la otra.

    Desambigua us/ms/s usando la duracion TIPICA de una palabra hablada
    (~0.3s). Una palabra cruda de 400 unidades son 0.0004s si fueran us
    (absurdo) o 0.4s si fueran ms (real, confirmado con datos reales de
    CapCut 8.8+: "vos"=[0,240] son 0 y 240 MILISEGUNDOS) -> elige ms.
    """
    candidatos = (1, 1000, 1_000_000)
    TARGET_US = 300_000  # duracion plausible de una palabra (~0.3s)
    if median_dur_raw and median_dur_raw > 0:
        return min(candidatos, key=lambda m: abs(median_dur_raw * m - TARGET_US))
    # respaldo: por magnitud del maximo vs duracion del video
    if duration_us and duration_us > 0 and max_raw > 0:
        for mult in candidatos:
            if max_raw * mult <= duration_us * 1.5:
                return mult
    if max_raw > 10_000_000:
        return 1
    return 1000

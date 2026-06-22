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

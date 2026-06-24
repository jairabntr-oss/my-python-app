"""Utilidades para parchear materiales de texto con una sola operación I/O."""

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple, Union

PatchValue = Union[Any, Callable[[Any, Dict[str, Any]], Any]]
PatchUpdates = Dict[str, PatchValue]


def patch_materials_batch(
    json_path: str, patches_list: Iterable[Tuple[str, PatchUpdates]]
) -> int:
    """Aplica parches por material_id sobre materials.texts en una sola escritura.

    Args:
        json_path: Ruta al draft_content.json.
        patches_list: Lista de tuplas (material_id, updates_dict).
            Si un valor de updates_dict es callable, se invoca como
            callable(valor_actual, material_actual) para calcular el nuevo valor.

    Returns:
        Cantidad de materiales parcheados.
    """
    patch_map: Dict[str, PatchUpdates] = {}
    for material_id, updates in patches_list:
        if not material_id or not updates:
            continue
        merged = patch_map.setdefault(material_id, {})
        merged.update(updates)
    if not patch_map:
        return 0

    path = Path(json_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    texts: List[Dict[str, Any]] = data.get("materials", {}).get("texts", []) or []
    patched = 0
    for mat in texts:
        material_id = mat.get("id")
        if material_id not in patch_map:
            continue
        for key, value in patch_map[material_id].items():
            if callable(value):
                mat[key] = value(mat.get(key), mat)
            else:
                mat[key] = value
        patched += 1

    if patched:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    return patched

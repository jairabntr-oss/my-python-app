import json

from core.json_patcher import patch_materials_batch


def test_patch_materials_batch_aplica_updates_y_callable(tmp_path):
    path = tmp_path / "draft_content.json"
    data = {
        "materials": {
            "texts": [
                {"id": "A", "content": json.dumps({"styles": [{}]})},
                {"id": "B", "content": json.dumps({"styles": [{}]})},
            ]
        }
    }
    path.write_text(json.dumps(data), encoding="utf-8")

    def patch_content(raw, _mat):
        obj = json.loads(raw)
        obj["patched"] = True
        return json.dumps(obj)

    patched = patch_materials_batch(
        str(path),
        [
            ("A", {"text_size": 30, "content": patch_content}),
            ("NO_EXISTE", {"text_size": 1}),
        ],
    )

    assert patched == 1
    out = json.loads(path.read_text(encoding="utf-8"))
    mats = {m["id"]: m for m in out["materials"]["texts"]}
    assert mats["A"]["text_size"] == 30
    assert json.loads(mats["A"]["content"])["patched"] is True
    assert "text_size" not in mats["B"]

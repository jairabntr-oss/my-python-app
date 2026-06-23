from utils.extract_autocaption import AutocaptionExtractor


def test_extraer_por_arrays_soporta_material_sin_id_y_ordena(monkeypatch):
    monkeypatch.setattr(AutocaptionExtractor, "_detectar_multiplicador", staticmethod(lambda *_: 1))

    stats = {"materiales_con_words": 0}
    materials_texts = [
        {
            "words": {
                "text": ["zeta"],
                "start_time": [2_000_000],
                "end_time": [2_200_000],
            }
        },
        {
            "id": "MAT1",
            "words": {
                "text": ["alfa"],
                "start_time": [0],
                "end_time": [100_000],
            },
        },
    ]
    draft = {
        "duration": 3_000_000,
        "tracks": [
            {
                "type": "text",
                "segments": [
                    {
                        "material_id": "MAT1",
                        "target_timerange": {"start": 1_000_000},
                    }
                ],
            }
        ],
    }

    oraciones = AutocaptionExtractor._extraer_por_arrays(materials_texts, draft, stats)
    assert stats["materiales_con_words"] == 2
    assert [o[0]["word"] for o in oraciones] == ["alfa", "zeta"]
    assert oraciones[0][0]["start_us"] == 1_000_000

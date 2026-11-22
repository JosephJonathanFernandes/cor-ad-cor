"""Unit tests for full Catechism (CCC §1–2865) JSON normalizer and section classifier."""

from __future__ import annotations

from app.rag.ccc_loader import classify_ccc_section, normalize_ccc_payload


def test_classify_ccc_sections() -> None:
    assert "Prologue" in classify_ccc_section(1)
    assert "Eucharist" in classify_ccc_section(1374)
    assert "Penance" in classify_ccc_section(1431)
    assert "Lord's Prayer" in classify_ccc_section(2865)


def test_normalize_diverse_ccc_json_shapes() -> None:
    # Shape 1: aseemsavio/catholicism-in-json style [{"id": N, "text": "..."}]
    records_list, report_list = normalize_ccc_payload(
        [
            {"id": 1431, "text": "  Interior   repentance is a radical reorientation.\n"},
            {"id": 1, "text": "God, infinitely perfect and blessed in himself."},
            {"id": 1, "text": "Short."},  # duplicate should keep longer text
        ]
    )
    assert report_list.total_paragraphs == 2
    assert report_list.duplicates_merged == 1
    assert records_list[0]["paragraph"] == 1
    assert "blessed in himself" in records_list[0]["text"]
    assert records_list[1]["paragraph"] == 1431
    assert "Penance" in records_list[1]["section"]

    # Shape 2: dict mapping paragraph number -> text
    records_dict, report_dict = normalize_ccc_payload(
        {"2729": "Dryness is a habitual difficulty in prayer.", "27": "The desire for God."}
    )
    assert report_dict.total_paragraphs == 2
    assert [r["paragraph"] for r in records_dict] == [27, 2729]

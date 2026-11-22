"""Normalizer, section classifier, and validator for full Catechism (CCC §1–2865) JSON corpora."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Canonical Catechism of the Catholic Church structural ranges (inclusive).
_CCC_SECTION_RANGES: list[tuple[int, int, str]] = [
    (1, 25, "Prologue — The Life of Man: To Know and Love God"),
    (26, 49, "Part I: Man's Capacity for God"),
    (50, 141, "Part I: God Comes to Meet Man (Revelation & Sacred Scripture)"),
    (142, 184, "Part I: Man's Response to God (Faith)"),
    (185, 421, "Part I: I Believe in God the Father (Creation, Providence & the Fall)"),
    (422, 682, "Part I: I Believe in Jesus Christ, the Only Son of God"),
    (683, 747, "Part I: I Believe in the Holy Spirit"),
    (748, 975, "Part I: The Holy Catholic Church & Communion of Saints"),
    (976, 1065, "Part I: Forgiveness of Sins, Resurrection & Life Everlasting"),
    (1066, 1209, "Part II: The Sacramental Economy & Liturgy"),
    (1210, 1284, "Part II: The Sacrament of Baptism"),
    (1285, 1321, "Part II: The Sacrament of Confirmation"),
    (1322, 1419, "Part II: The Sacrament of the Eucharist"),
    (1420, 1498, "Part II: The Sacrament of Penance and Reconciliation"),
    (1499, 1532, "Part II: The Anointing of the Sick"),
    (1533, 1600, "Part II: The Sacrament of Holy Orders"),
    (1601, 1666, "Part II: The Sacrament of Matrimony"),
    (1667, 1690, "Part II: Sacramentals & Christian Funerals"),
    (1691, 1761, "Part III: Man's Vocation — Dignity, Beatitudes & Freedom"),
    (1762, 1845, "Part III: Passions, Moral Conscience, Virtues & Charity"),
    (1846, 1876, "Part III: Sin and Mercy"),
    (1877, 1948, "Part III: The Human Community & Social Justice"),
    (1949, 2051, "Part III: God's Salvation — Law and Grace"),
    (2052, 2195, "Part III: The First Three Commandments (Love of God)"),
    (2196, 2557, "Part III: Commandments Four to Ten (Love of Neighbor)"),
    (2558, 2649, "Part IV: Prayer in the Christian Life"),
    (2650, 2696, "Part IV: The Tradition of Prayer"),
    (2697, 2758, "Part IV: The Life of Prayer (Vocal, Meditation, Contemplation & Battle)"),
    (2759, 2865, "Part IV: The Lord's Prayer — Our Father"),
]


def classify_ccc_section(paragraph: int) -> str:
    """Return the canonical Catechism Part/Section title for a paragraph number."""
    for start, end, title in _CCC_SECTION_RANGES:
        if start <= paragraph <= end:
            return title
    return "Catechism of the Catholic Church"


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned


def _extract_paragraph_number(raw_key: Any) -> int | None:
    if isinstance(raw_key, int):
        return raw_key
    if isinstance(raw_key, str):
        match = re.search(r"\d+", raw_key)
        if match:
            return int(match.group(0))
    return None


@dataclass(frozen=True)
class CCCValidationReport:
    """Summary of normalized CCC corpus quality and paragraph coverage."""

    total_paragraphs: int
    min_paragraph: int
    max_paragraph: int
    missing_in_1_to_2865: list[int]
    duplicates_merged: int


def normalize_ccc_payload(
    raw_payload: Any,
    *,
    source_type: str = "official_text",
) -> tuple[list[dict[str, Any]], CCCValidationReport]:
    """Normalize diverse CCC JSON formats into our canonical `ccc_full.json` list schema.

    Supported input shapes:
      - list of {"id": 1, "text": "..."} (e.g., aseemsavio/catholicism-in-json)
      - list of {"paragraph": 1, "section": "...", "text": "..."}
      - list of {"number": 1, "content": "..."}
      - dict mapping "1": "..." or {"paragraphs": [...]} / {"catechism": [...]}
    """
    items: list[tuple[int, str, str]] = []

    if isinstance(raw_payload, dict):
        for container_key in ("paragraphs", "catechism", "data", "items"):
            if isinstance(raw_payload.get(container_key), list):
                raw_payload = raw_payload[container_key]
                break

    if isinstance(raw_payload, dict):
        for key, value in raw_payload.items():
            num = _extract_paragraph_number(key)
            if num is None:
                continue
            if isinstance(value, str):
                items.append((num, "", value))
            elif isinstance(value, dict):
                txt = str(value.get("text") or value.get("content") or value.get("body") or "")
                sec = str(value.get("section") or value.get("title") or "")
                items.append((num, sec, txt))
    elif isinstance(raw_payload, list):
        for entry in raw_payload:
            if not isinstance(entry, dict):
                continue
            num = _extract_paragraph_number(
                entry.get("paragraph")
                if entry.get("paragraph") is not None
                else entry.get("id")
                if entry.get("id") is not None
                else entry.get("number")
                if entry.get("number") is not None
                else entry.get("para")
            )
            if num is None or num < 1:
                continue
            txt = str(
                entry.get("text")
                or entry.get("content")
                or entry.get("body")
                or entry.get("paragraph_text")
                or ""
            )
            sec = str(entry.get("section") or entry.get("title") or "")
            items.append((num, sec, txt))
    else:
        raise ValueError(f"Unsupported CCC JSON root type: {type(raw_payload).__name__}")

    by_paragraph: dict[int, dict[str, Any]] = {}
    duplicates = 0

    for num, section, raw_text in items:
        text = _clean_text(raw_text)
        if not text:
            continue
        if num in by_paragraph:
            duplicates += 1
            # Keep the longer / cleaner text if a duplicate appears
            if len(text) <= len(by_paragraph[num]["text"]):
                continue
        resolved_section = section.strip() or classify_ccc_section(num)
        by_paragraph[num] = {
            "paragraph": num,
            "section": resolved_section,
            "text": text,
            "source_type": source_type,
        }

    ordered = [by_paragraph[k] for k in sorted(by_paragraph)]
    if not ordered:
        raise ValueError("No valid Catechism paragraphs could be extracted from input payload.")

    present = set(by_paragraph.keys())
    missing = [p for p in range(1, 2866) if p not in present]
    report = CCCValidationReport(
        total_paragraphs=len(ordered),
        min_paragraph=ordered[0]["paragraph"],
        max_paragraph=ordered[-1]["paragraph"],
        missing_in_1_to_2865=missing,
        duplicates_merged=duplicates,
    )
    return ordered, report


def save_normalized_ccc(records: list[dict[str, Any]], output_path: Path) -> None:
    """Write normalized CCC JSON records to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

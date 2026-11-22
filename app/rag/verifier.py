"""Post-generation Catechism citation verifier and auto-hydrator (anti-hallucination guardrail)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.rag.catechism import CatechismHit, CatechismIndex

_CCC_CITATION_RE = re.compile(r"\[CCC\s*§?\s*(\d+)\]", re.I)


@dataclass(frozen=True)
class CitationVerification:
    """Audit result for every [CCC §N] citation appearing in a generated reflection."""

    cited_paragraphs: list[int] = field(default_factory=list)
    verified_paragraphs: list[int] = field(default_factory=list)
    hydrated_paragraphs: list[int] = field(default_factory=list)
    unverified_paragraphs: list[int] = field(default_factory=list)

    @property
    def all_valid(self) -> bool:
        return len(self.unverified_paragraphs) == 0


def verify_and_hydrate_citations(
    reflection_text: str,
    retrieved_hits: list[CatechismHit],
    ccc_index: CatechismIndex,
) -> tuple[list[CatechismHit], CitationVerification]:
    """Verify every [CCC §N] tag in `reflection_text` against the Catechism index.

    - Valid citations already in `retrieved_hits` are marked verified.
    - Valid citations present in `ccc_index` (e.g. from the full 2,865-paragraph CCC)
      are auto-hydrated into the returned hits list so UI pills always open the real text.
    - Out-of-range or unknown paragraph numbers are recorded in `unverified_paragraphs`.
    """
    hits_by_num: dict[int, CatechismHit] = {hit.paragraph: hit for hit in retrieved_hits}
    ordered_hits: list[CatechismHit] = list(retrieved_hits)

    cited: list[int] = []
    verified: list[int] = []
    hydrated: list[int] = []
    unverified: list[int] = []

    for match in _CCC_CITATION_RE.finditer(reflection_text):
        num = int(match.group(1))
        if num in cited:
            continue
        cited.append(num)

        if num in hits_by_num:
            verified.append(num)
            continue

        looked_up = ccc_index.get_by_paragraph(num)
        if looked_up is not None:
            verified.append(num)
            hydrated.append(num)
            hits_by_num[num] = looked_up
            ordered_hits.append(looked_up)
        else:
            unverified.append(num)

    return ordered_hits, CitationVerification(
        cited_paragraphs=cited,
        verified_paragraphs=verified,
        hydrated_paragraphs=hydrated,
        unverified_paragraphs=unverified,
    )

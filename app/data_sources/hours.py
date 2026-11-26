"""Liturgy of the Hours canticles and season-aware Angelus / Regina Caeli prayers."""

from __future__ import annotations

from dataclasses import asdict, dataclass


ANGELUS_TEXT = (
    "℣. The Angel of the Lord declared unto Mary.\n"
    "℟. And she conceived of the Holy Spirit.\n"
    "(Hail Mary...)\n\n"
    "℣. Behold the handmaid of the Lord.\n"
    "℟. Be it done unto me according to thy word.\n"
    "(Hail Mary...)\n\n"
    "℣. And the Word was made flesh.\n"
    "℟. And dwelt among us.\n"
    "(Hail Mary...)\n\n"
    "℣. Pray for us, O holy Mother of God.\n"
    "℟. That we may be made worthy of the promises of Christ.\n\n"
    "Let us pray: Pour forth, we beseech thee, O Lord, thy grace into our hearts; that we, to whom "
    "the Incarnation of Christ, thy Son, was made known by the message of an angel, may by his "
    "Passion and Cross be brought to the glory of his Resurrection, through the same Christ our Lord. Amen."
)

REGINA_CAELI_TEXT = (
    "℣. Queen of Heaven, rejoice, alleluia.\n"
    "℟. For He whom you did merit to bear, alleluia.\n\n"
    "℣. Has risen, as he said, alleluia.\n"
    "℟. Pray for us to God, alleluia.\n\n"
    "℣. Rejoice and be glad, O Virgin Mary, alleluia.\n"
    "℟. For the Lord has truly risen, alleluia.\n\n"
    "Let us pray: O God, who gave joy to the world through the resurrection of thy Son, our Lord "
    "Jesus Christ, grant we beseech thee, that through the intercession of the Virgin Mary, his "
    "Mother, we may obtain the joys of everlasting life. Through the same Christ our Lord. Amen."
)

BENEDICTUS_TEXT = (
    "Blessed be the Lord, the God of Israel; he has come to his people and set them free. "
    "He has raised up for us a mighty savior, born of the house of his servant David. "
    "In the tender compassion of our God the dawn from on high shall break upon us, "
    "to shine on those who dwell in darkness and the shadow of death, and to guide our feet into the way of peace."
)

MAGNIFICAT_TEXT = (
    "My soul proclaims the greatness of the Lord, my spirit rejoices in God my Savior, "
    "for he has looked with favor on his lowly servant. From this day all generations will call me blessed: "
    "the Almighty has done great things for me, and holy is his Name. He has mercy on those who fear him "
    "in every generation."
)

NUNC_DIMITTIS_TEXT = (
    "Lord, now you let your servant go in peace; your word has been fulfilled: "
    "my own eyes have seen the salvation which you have prepared in the sight of every people: "
    "a light to reveal you to the nations and the glory of your people Israel."
)


@dataclass(frozen=True)
class HourPrayer:
    """Prayer context for the current liturgical hour of the day."""

    hour_key: str
    label: str
    recommended_tab: str
    marian_devotion_title: str
    marian_devotion_text: str
    canticle_title: str
    canticle_citation: str
    canticle_text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def get_prayer_for_hour(hour: int, season: str = "Ordinary Time") -> HourPrayer:
    """Return the Gospel Canticle and Angelus/Regina Caeli matched to local hour (0–23) and season."""
    h = hour % 24
    is_easter = "easter" in (season or "").lower()
    devotion_title = "Regina Caeli (Easter Time)" if is_easter else "The Angelus"
    devotion_text = REGINA_CAELI_TEXT if is_easter else ANGELUS_TEXT

    if 5 <= h < 11:
        return HourPrayer(
            hour_key="lauds",
            label="Lauds • Morning Prayer",
            recommended_tab="daily",
            marian_devotion_title=devotion_title,
            marian_devotion_text=devotion_text,
            canticle_title="Canticle of Zechariah (Benedictus)",
            canticle_citation="Luke 1:68-79",
            canticle_text=BENEDICTUS_TEXT,
        )
    if 11 <= h < 15:
        return HourPrayer(
            hour_key="midday",
            label="Midday • The Angelus Hour",
            recommended_tab="lectio",
            marian_devotion_title=devotion_title,
            marian_devotion_text=devotion_text,
            canticle_title="Psalm 23 — The Good Shepherd",
            canticle_citation="Psalm 23:1-3",
            canticle_text="The Lord is my shepherd; there is nothing I shall want. Fresh and green are the pastures where he gives me repose; near restful waters he leads me, to revive my drooping spirit.",
        )
    if 15 <= h < 20:
        return HourPrayer(
            hour_key="vespers",
            label="Vespers • Evening Prayer",
            recommended_tab="checkin",
            marian_devotion_title=devotion_title,
            marian_devotion_text=devotion_text,
            canticle_title="Canticle of Mary (Magnificat)",
            canticle_citation="Luke 1:46-55",
            canticle_text=MAGNIFICAT_TEXT,
        )
    return HourPrayer(
        hour_key="compline",
        label="Compline • Night Prayer",
        recommended_tab="examen",
        marian_devotion_title=devotion_title,
        marian_devotion_text=devotion_text,
        canticle_title="Canticle of Simeon (Nunc Dimittis)",
        canticle_citation="Luke 2:29-32",
        canticle_text=NUNC_DIMITTIS_TEXT,
    )

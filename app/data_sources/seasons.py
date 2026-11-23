"""Catholic liturgical season guidance, vestment color meanings, and seasonal Marian antiphons."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SeasonGuide:
    """Pastoral and liturgical context for the current season and vestment color."""

    season_key: str
    display_name: str
    colour_meaning: str
    spiritual_focus: str
    marian_antiphon_title: str
    marian_antiphon_text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_COLOUR_MEANINGS: dict[str, str] = {
    "white": "White / Gold signifies joy, purity, and the glory of Christ's resurrection and the saints.",
    "gold": "White / Gold signifies joy, purity, and the glory of Christ's resurrection and the saints.",
    "green": "Green signifies hope, growth, and steady discipleship in the ordinary days of the year.",
    "violet": "Violet signifies penance, preparation, humility, and watchful waiting for the Lord.",
    "purple": "Violet signifies penance, preparation, humility, and watchful waiting for the Lord.",
    "red": "Red signifies the fire of the Holy Spirit and the self-giving love of Christ and the martyrs.",
    "rose": "Rose signifies a brief, gentle pause of joy in the midst of Advent or Lenten penance.",
}

_SEASON_GUIDES: dict[str, tuple[str, str, str, str]] = {
    "advent": (
        "Advent",
        "Watchful waiting, honest longing, and making room for Christ who comes in quietness.",
        "Alma Redemptoris Mater (Advent & Christmas)",
        "Loving Mother of the Redeemer, gate of heaven, star of the sea, assist your people who have fallen yet strive to rise again. To the wonderment of nature you bore your Creator, yet remained a virgin after as before. You who received Gabriel's joyful greeting, have pity on us poor sinners.",
    ),
    "christmas": (
        "Christmas Time",
        "Wonder at the Incarnation—God entering human smallness, family life, and ordinary vulnerability.",
        "Alma Redemptoris Mater (Advent & Christmas)",
        "Loving Mother of the Redeemer, gate of heaven, star of the sea, assist your people who have fallen yet strive to rise again. To the wonderment of nature you bore your Creator, yet remained a virgin after as before. You who received Gabriel's joyful greeting, have pity on us poor sinners.",
    ),
    "lent": (
        "Lent",
        "Desert honesty, returning to the Father with all our heart through prayer, fasting, and mercy.",
        "Ave Regina Caelorum (Lent)",
        "Hail, Queen of heaven. Hail, Lady of Angels. Hail, thou root, hail, thou gate from whom unto the world a light has arisen: Rejoice, O glorious Virgin, lovely beyond all others, farewell, most beautiful maiden, and pray for us to Christ.",
    ),
    "easter": (
        "Easter Time",
        "Living from the reality of the Resurrection—hope stronger than fear, peace, and Spirit-led mission.",
        "Regina Caeli (Easter Time)",
        "Queen of Heaven, rejoice, alleluia. For He whom you did merit to bear, alleluia, has risen, as he said, alleluia. Pray for us to God, alleluia. Rejoice and be glad, O Virgin Mary, alleluia, for the Lord has truly risen, alleluia.",
    ),
    "ordinary": (
        "Ordinary Time",
        "Quiet, steady faithfulness—letting the Gospel reshape daily work, relationships, and hidden choices.",
        "Salve Regina (Hail, Holy Queen)",
        "Hail, holy Queen, Mother of mercy, our life, our sweetness, and our hope. To thee do we cry, poor banished children of Eve; to thee do we send up our sighs, mourning and weeping in this valley of tears. Turn then, most gracious advocate, thine eyes of mercy toward us; and after this our exile, show unto us the blessed fruit of thy womb, Jesus.",
    ),
}


def get_season_guide(season: str, colour: str = "") -> SeasonGuide:
    """Return seasonal spiritual focus, vestment color meaning, and Compline Marian antiphon."""
    lower = (season or "").strip().lower()
    if "advent" in lower:
        key = "advent"
    elif "christmas" in lower:
        key = "christmas"
    elif "lent" in lower or "holy week" in lower or "triduum" in lower:
        key = "lent"
    elif "easter" in lower:
        key = "easter"
    else:
        key = "ordinary"

    display_name, focus, antiphon_title, antiphon_text = _SEASON_GUIDES[key]
    colour_key = (colour or "").strip().lower()
    colour_meaning = _COLOUR_MEANINGS.get(
        colour_key,
        "Liturgical colors visibly echo the Church's prayer and season at Mass.",
    )
    return SeasonGuide(
        season_key=key,
        display_name=display_name,
        colour_meaning=colour_meaning,
        spiritual_focus=focus,
        marian_antiphon_title=antiphon_title,
        marian_antiphon_text=antiphon_text,
    )

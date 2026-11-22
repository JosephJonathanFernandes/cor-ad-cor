"""Classic Catholic Prayer Treasury for offline, instant prayerful grounding."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CatholicPrayer:
    """A traditional Catholic prayer categorized by moment of the day or need."""

    slug: str
    title: str
    moment: str
    attribution: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


PRAYER_TREASURY: list[CatholicPrayer] = [
    CatholicPrayer(
        slug="morning-offering",
        title="Morning Offering",
        moment="morning",
        attribution="Traditional Catholic Prayer",
        text=(
            "O Jesus, through the Immaculate Heart of Mary, I offer you my prayers, works, joys, "
            "and sufferings of this day for all the intentions of your Sacred Heart, in union with "
            "the Holy Sacrifice of the Mass throughout the world, for the salvation of souls, the "
            "reparation of sins, the reunion of all Christians, and in particular for the intentions "
            "of the Holy Father this month. Amen."
        ),
    ),
    CatholicPrayer(
        slug="suscipe",
        title="Suscipe (Take, Lord, and Receive)",
        moment="trust",
        attribution="St. Ignatius of Loyola",
        text=(
            "Take, Lord, and receive all my liberty, my memory, my understanding, and my entire will—"
            "all that I have and call my own. You have given all to me. To you, Lord, I return it. "
            "Everything is yours; do with it what you will. Give me only your love and your grace; "
            "that is enough for me. Amen."
        ),
    ),
    CatholicPrayer(
        slug="anima-christi",
        title="Anima Christi (Soul of Christ)",
        moment="eucharist",
        attribution="14th-Century Eucharistic Prayer",
        text=(
            "Soul of Christ, sanctify me. Body of Christ, save me. Blood of Christ, inebriate me. "
            "Water from the side of Christ, wash me. Passion of Christ, strengthen me. O good Jesus, "
            "hear me. Within your wounds hide me. Permit me not to be separated from you. From the "
            "wicked foe defend me. At the hour of my death call me, and bid me come to you, that with "
            "your saints I may praise you forever and ever. Amen."
        ),
    ),
    CatholicPrayer(
        slug="act-of-contrition",
        title="Act of Contrition",
        moment="confession",
        attribution="Rite of Penance",
        text=(
            "My God, I am sorry for my sins with all my heart. In choosing to do wrong and failing "
            "to do good, I have sinned against you whom I should love above all things. I firmly intend, "
            "with your help, to do penance, to sin no more, and to avoid whatever leads me to sin. "
            "Our Savior Jesus Christ suffered and died for us. In his name, my God, have mercy. Amen."
        ),
    ),
    CatholicPrayer(
        slug="memorare",
        title="The Memorare",
        moment="trust",
        attribution="Traditional Marian Prayer",
        text=(
            "Remember, O most gracious Virgin Mary, that never was it known that anyone who fled to "
            "your protection, implored your help, or sought your intercession was left unaided. "
            "Inspired by this confidence, I fly unto you, O Virgin of virgins, my Mother. To you do "
            "I come, before you I stand, sinful and sorrowful. O Mother of the Word Incarnate, despise "
            "not my petitions, but in your mercy hear and answer me. Amen."
        ),
    ),
    CatholicPrayer(
        slug="come-holy-spirit",
        title="Come, Holy Spirit",
        moment="morning",
        attribution="Pentecost Sequence / Traditional",
        text=(
            "Come, Holy Spirit, fill the hearts of your faithful and kindle in them the fire of your "
            "love. Send forth your Spirit and they shall be created, and you shall renew the face of "
            "the earth. O God, who by the light of the Holy Spirit did instruct the hearts of the "
            "faithful, grant that by the same Holy Spirit we may be truly wise and ever enjoy his "
            "consolations, through Christ our Lord. Amen."
        ),
    ),
    CatholicPrayer(
        slug="st-teresa-bookmark",
        title="Let Nothing Disturb You",
        moment="trust",
        attribution="St. Teresa of Avila",
        text=(
            "Let nothing disturb you, let nothing frighten you. All things are passing away; God "
            "never changes. Patience obtains all things. Whoever has God lacks nothing; God alone "
            "suffices. Amen."
        ),
    ),
    CatholicPrayer(
        slug="compline-night",
        title="Night Prayer (Compline Antiphon)",
        moment="evening",
        attribution="Liturgy of the Hours — Night Prayer",
        text=(
            "Protect us, Lord, as we stay awake; watch over us as we sleep, that awake, we may keep "
            "watch with Christ, and asleep, rest in his peace. May the all-powerful Lord grant us a "
            "restful night and a peaceful death. Amen."
        ),
    ),
]


def list_prayers(moment: str | None = None) -> list[CatholicPrayer]:
    """Return all prayers or filter by moment/keyword (morning, evening, confession, trust, eucharist)."""
    if not moment or not moment.strip():
        return list(PRAYER_TREASURY)
    needle = moment.strip().lower()
    matched = [
        p
        for p in PRAYER_TREASURY
        if needle in p.moment.lower() or needle in p.title.lower() or needle in p.slug.lower()
    ]
    return matched or list(PRAYER_TREASURY)

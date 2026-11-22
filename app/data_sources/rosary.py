"""Guided Catholic Rosary Mysteries of the Day with Scripture, Fruits, and CCC anchors."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RosaryMystery:
    """One decade of the Rosary with Scripture, traditional fruit, CCC anchor, and intention."""

    number: int
    title: str
    scripture: str
    fruit: str
    ccc_paragraph: int
    intention: str


@dataclass(frozen=True)
class RosaryDay:
    """Complete 5-decade Rosary set for a given date."""

    date: str
    weekday: str
    mystery_set: str
    mysteries: list[RosaryMystery]

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "weekday": self.weekday,
            "mystery_set": self.mystery_set,
            "mysteries": [asdict(m) for m in self.mysteries],
        }


_ROSARY_SETS: dict[str, list[RosaryMystery]] = {
    "Joyful Mysteries": [
        RosaryMystery(1, "The Annunciation", "Luke 1:26-38", "Humility", 494, "Notice where God may be inviting a quiet, unhurried 'yes' in the middle of your ordinary plans."),
        RosaryMystery(2, "The Visitation", "Luke 1:39-56", "Love of Neighbor", 717, "Bring to mind one person who feels unseen today and carry them gently in this decade."),
        RosaryMystery(3, "The Nativity of Our Lord", "Luke 2:1-20", "Poverty of Spirit", 525, "Rest in the truth that Christ enters our lives not when everything is tidy, but right in our smallness."),
        RosaryMystery(4, "The Presentation in the Temple", "Luke 2:22-38", "Obedience & Surrender", 529, "Offer back to God one outcome or relationship you have been clutching tightly."),
        RosaryMystery(5, "The Finding of Jesus in the Temple", "Luke 2:41-52", "Joy in Finding Jesus", 534, "When God feels hard to locate, ask for the quiet perseverance to keep seeking him honestly."),
    ],
    "Luminous Mysteries": [
        RosaryMystery(1, "The Baptism of Jesus in the Jordan", "Matthew 3:13-17", "Openness to the Holy Spirit", 535, "Sit with the Father's voice over Christ—and over you in Baptism: 'You are my beloved.'"),
        RosaryMystery(2, "The Wedding Feast at Cana", "John 2:1-12", "To Jesus Through Mary", 2618, "Name plainly where your own wine—your energy, patience, or hope—has run dry today."),
        RosaryMystery(3, "The Proclamation of the Kingdom", "Mark 1:14-15", "Repentance & Trust", 1431, "Ask for a gentle turning of heart away from old habits and toward Christ's mercy."),
        RosaryMystery(4, "The Transfiguration", "Luke 9:28-36", "Desire for Holiness", 554, "Receive one glimpse of Christ's light to carry with you down the mountain into ordinary work."),
        RosaryMystery(5, "The Institution of the Eucharist", "Matthew 26:26-29", "Adoration", 1324, "Thank Christ for remaining truly, really, and substantially present to nourish tired disciples."),
    ],
    "Sorrowful Mysteries": [
        RosaryMystery(1, "The Agony in the Garden", "Matthew 26:36-46", "Sorrow for Sin & Trust", 612, "Bring your own anxiety or dread into Gethsemane—Jesus knows what it is to pray in the dark."),
        RosaryMystery(2, "The Scourging at the Pillar", "John 19:1", "Purity & Healing", 609, "Place physical exhaustion, woundedness, or temptation gently beside Christ's endurance."),
        RosaryMystery(3, "The Crowning with Thorns", "Matthew 27:27-31", "Courage & Humility", 572, "Offer up the sting of being misunderstood, criticized, or humbled without retaliating."),
        RosaryMystery(4, "The Carrying of the Cross", "Luke 23:26-32", "Patience in Suffering", 618, "Walk this decade slowly with the weight you didn't choose, letting Christ share the beam."),
        RosaryMystery(5, "The Crucifixion and Death of Jesus", "John 19:25-30", "Perseverance & Forgiveness", 616, "Ask for the grace to forgive one real hurt, trusting God's mercy even at the foot of the Cross."),
    ],
    "Glorious Mysteries": [
        RosaryMystery(1, "The Resurrection", "Mark 16:1-7", "Faith", 638, "Bring one place in your life that feels closed or tomb-like and ask the Risen Lord to breathe into it."),
        RosaryMystery(2, "The Ascension", "Acts 1:6-11", "Hope", 665, "Lift your eyes beyond today's noise toward the enduring home Christ prepares for you."),
        RosaryMystery(3, "The Descent of the Holy Spirit", "Acts 2:1-13", "Wisdom & Love of God", 731, "Invite the Holy Spirit into one conversation or decision where you need clarity and gentleness."),
        RosaryMystery(4, "The Assumption of Mary", "Revelation 12:1", "Grace of a Happy Death", 966, "Trust that God honors quiet, faithful love and brings every redeemed life safely home."),
        RosaryMystery(5, "The Coronation of Mary", "Revelation 12:1-6", "Trust in Mary's Intercession", 956, "Rest in the Communion of Saints—you are never praying alone in the Church."),
    ],
}

# Monday=0 .. Sunday=6
_WEEKDAY_TO_MYSTERY: dict[int, str] = {
    0: "Joyful Mysteries",
    1: "Sorrowful Mysteries",
    2: "Glorious Mysteries",
    3: "Luminous Mysteries",
    4: "Sorrowful Mysteries",
    5: "Joyful Mysteries",
    6: "Glorious Mysteries",
}


def get_rosary_for_date(target_date: dt.date | None = None) -> RosaryDay:
    """Return the traditional Catholic Rosary Mysteries for the given date."""
    resolved = target_date or dt.date.today()
    mystery_set = _WEEKDAY_TO_MYSTERY[resolved.weekday()]
    return RosaryDay(
        date=resolved.isoformat(),
        weekday=resolved.strftime("%A"),
        mystery_set=mystery_set,
        mysteries=_ROSARY_SETS[mystery_set],
    )

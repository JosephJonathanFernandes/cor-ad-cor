"""Catholic spiritual companion voice, prompt builders, and pastoral guardrails."""

from __future__ import annotations

import re

from app.data_sources.liturgy import LiturgicalDay
from app.rag.catechism import CatechismHit

COMPANION_SYSTEM_PROMPT = """You are "Cor ad Cor", a compassionate Catholic spiritual companion.

VOICE & REGISTER:
- Speak like a warm, unhurried, attentive therapist-like spiritual companion—grounded in historic Catholic faith rather than generic secular self-help.
- Use reflective language ("You might notice...", "It's worth sitting with...", "Notice what stirs when...") rather than lecturing or commanding.
- Sit with difficulty first. When a reading or user touches grief, exhaustion, doubt, or dryness, honor that weight honestly before pointing toward hope.
- Ask gentle, concrete questions that open prayerful reflection instead of closing everything into a tidy slogan.
- Translate theological jargon and ancient cultural references (denarius, yoke, Pharisee, justification, concupiscence) into clear everyday words without dropping the truth inside them.

THEOLOGICAL & PASTORAL GUARDRAILS:
1. Never flatten Mystery: Keep mysteries such as the Trinity, the Real Presence in the Eucharist, and redemptive suffering intact. Clarity means accessible language, not shrinking God down.
2. Never soften Catholic doctrine: Present Church teaching on mercy, sin, grace, and moral truth clearly and charitably rather than hedging into vague self-help.
3. Strict Citation Grounding: Ground every scriptural or doctrinal claim in the provided context using explicit bracketed tags like [First Reading], [Responsorial Psalm], [Gospel], [Saint], or [CCC §N]. NEVER invent a Bible verse or CCC paragraph number that was not provided.
4. Preserve Attribution: Keep clear whose voice is speaking (Scripture vs. Catechism vs. Saint's life vs. your own reflection).
5. Clear Boundaries: You are a prayerful companion, NOT a licensed therapist, medical doctor, or priest. You cannot hear Confession or grant sacramental absolution. When appropriate, gently encourage bringing heavy burdens to a priest in Confession, a spiritual director, or a qualified counselor."""

_DISTRESS_PATTERNS = [
    re.compile(r"\b(kill myself|end my life|suicid(e|al)|want to die|self[- ]?harm|hurt myself)\b", re.I),
    re.compile(r"\b(no reason to live|better off dead|can'?t go on)\b", re.I),
]

PASTORAL_CRISIS_RESPONSE = (
    "I'm really glad you didn't stay silent with something this heavy, and I want to pause right here with care. "
    "What you're carrying sounds too weighty to hold alone, and as a software companion I can't give you the real human care you deserve right now.\n\n"
    "Please reach out to someone who can sit with you in person or by voice today:\n"
    "- **If you are in immediate danger or thinking of hurting yourself:** call or text **988** (Suicide & Crisis Lifeline in the US/Canada), text **HOME to 741741**, or contact your local emergency services / crisis line right away.\n"
    "- **Reach out to a trusted person:** a close friend, family member, licensed counselor, or your parish priest.\n\n"
    "The Church holds that your life is deeply sacred ([CCC §2258]), and God does not abandon you in the dark. Please let a real human voice walk with you tonight."
)


def detect_distress_signal(text: str) -> bool:
    """Return True if user text expresses acute self-harm or suicidal distress."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return any(pattern.search(cleaned) for pattern in _DISTRESS_PATTERNS)


def _format_liturgy_context(day: LiturgicalDay) -> str:
    lines = [
        f"Date: {day.date}",
        f"Liturgical Season: {day.season}",
        f"Celebration: {day.celebration_title or 'Weekday'}",
    ]
    if day.saint:
        lines.append(
            f"[Saint] {day.saint.title} (Rank: {day.saint.rank or 'N/A'}) — {day.saint.summary}"
        )
    for reading in day.readings:
        lines.append(f"\n[{reading.label}] ({reading.citation})\n{reading.text}")
    if day.papal_reflection:
        lines.append(f"\n[Words of the Popes]\n{day.papal_reflection}")
    return "\n".join(lines)


def _format_ccc_context(hits: list[CatechismHit]) -> str:
    if not hits:
        return "No Catechism paragraphs were retrieved."
    blocks = []
    for hit in hits:
        note = " (concise summary)" if hit.source_type == "seed_summary" else ""
        blocks.append(f"[{hit.citation}] {hit.section}{note}:\n{hit.text}")
    return "\n\n".join(blocks)


def build_daily_briefing_prompt(day: LiturgicalDay, ccc_hits: list[CatechismHit]) -> str:
    """Build the user prompt for the morning / pre-Mass daily briefing."""
    return f"""Prepare today's grounded Catholic daily reflection using ONLY the liturgical texts, saint context, and Catechism paragraphs below.

=== LITURGICAL CONTEXT ===
{_format_liturgy_context(day)}

=== RETRIEVED CATECHISM PARAGRAPHS ===
{_format_ccc_context(ccc_hits)}

Write the reflection using these exact markdown headings:

### 1. 5 Minutes Before Mass (Setting the Scene)
Explain in plain, vivid language who is speaking, any historical or cultural details (names, customs, words that carry hidden weight), and what is actually happening in the readings. Cite [First Reading], [Responsorial Psalm], [Gospel] (and [Second Reading] if present).

### 2. The Hidden Thread
Explain in 1 short paragraph why the Church paired today's readings together—what common human struggle or promise runs through them.

### 3. Saint of the Day & Living Witness
Give a brief, warm reflection on today's [Saint] (if present in context) and how their life connects naturally to today's readings. Do not invent biographical facts not in the context; if only the title/rank is provided, reflect humbly on what that feast signifies in the Church's year.

### 4. Catechism Anchor
Weave 1–2 of the retrieved [CCC §N] paragraphs into plain, heartfelt language showing how the Church's teaching deepens today's Gospel. Keep exact [CCC §N] citations.

### 5. One Question to Carry & A Short Prayer
- End with **one** honest, open-ended question the reader can sit with today.
- Follow with a brief 2–3 sentence prayer."""


def build_checkin_prompt(
    user_note: str,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    *,
    memory_context: str = "",
) -> str:
    """Build the user prompt for a personal 'Bring Your Day to Mass' check-in."""
    memory_block = (
        f"\n=== SEASON CONTINUITY (OPT-IN PRIVATE MEMORY) ===\n{memory_context}\n"
        if memory_context
        else ""
    )
    return f"""A user has shared something honest they are carrying today and wants to bring it alongside today's Mass readings and Catholic teaching.

=== WHAT THE USER SHARED ===
"{user_note.strip()}"
{memory_block}
=== TODAY'S LITURGICAL CONTEXT ===
{_format_liturgy_context(day)}

=== RETRIEVED CATECHISM PARAGRAPHS ===
{_format_ccc_context(ccc_hits)}

Respond in the compassionate spiritual companion voice:
1. **Acknowledge First:** Meet what they shared with warmth and zero judgment. Don't rush to fix it or offer toxic positivity. If season continuity notes show a recurring theme, notice it gently without sounding clinical.
2. **Bridge to Today's Word:** Gently show how something in today's readings ([First Reading], [Responsorial Psalm], [Gospel]) or [Saint] speaks into that exact place—without forcing a fake connection.
3. **Catechism Grounding:** Connect 1 retrieved [CCC §N] paragraph clearly in plain words, keeping the exact [CCC §N] citation.
4. **Two Honest Questions:** Offer 1–2 unhurried questions they can sit with in prayer today.
5. **Small Concrete Anchor:** End with a short 2-sentence prayer (and if their struggle touches deep guilt or spiritual discernment, gently mention talking with a priest in Confession or a trusted spiritual director/counselor as a real next step)."""


def build_preview_daily_reflection(day: LiturgicalDay, ccc_hits: list[CatechismHit]) -> str:
    """Build a deterministic, citation-grounded preview briefing when no LLM keys are configured."""
    first = day.readings[0] if day.readings else None
    gospel = next((r for r in day.readings if "gospel" in r.label.lower()), first)
    saint_title = day.saint.title if day.saint else (day.celebration_title or "today's liturgical feast")
    ccc_primary = ccc_hits[0] if ccc_hits else None
    ccc_secondary = ccc_hits[1] if len(ccc_hits) > 1 else ccc_primary

    first_ref = f"[{first.label}] ({first.citation})" if first else "[First Reading]"
    gospel_ref = f"[{gospel.label}] ({gospel.citation})" if gospel else "[Gospel]"
    ccc_ref_1 = f"[{ccc_primary.citation}]" if ccc_primary else "[CCC §27]"
    ccc_ref_2 = f"[{ccc_secondary.citation}]" if ccc_secondary else ccc_ref_1

    return f"""### 1. 5 Minutes Before Mass (Setting the Scene)
In today's liturgy for **{day.celebration_title or day.season}**, the Church invites us to slow down and listen beneath the surface of the text. In {first_ref}, we hear a promise of God drawing near to dwell with his people—not as a distant ruler, but right in the middle of ordinary life. Then in {gospel_ref}, the scene shifts to a crowded room where Jesus redefines closeness to him: belonging isn't restricted to status or pedigree, but opens to anyone willing to listen and do the Father's will.

### 2. The Hidden Thread
Notice why the Church pairs {first_ref} with {gospel_ref} today: the first reading speaks of God making a home among us, while the Gospel shows what that home looks like on the inside—a family formed by attentive, everyday trust in God's word.

### 3. Saint of the Day & Living Witness
Today we remember **[Saint] {saint_title}**. {day.saint.summary if day.saint else "In the rhythm of the liturgical year, the saints remind us that holiness is lived one faithful yes at a time."} It's worth sitting with how quiet availability to God—rather than having everything figured out—creates space for grace.

### 4. Catechism Anchor
The Catechism gently anchors this in {ccc_ref_1} (*{ccc_primary.section if ccc_primary else "The Desire for God"}*): {ccc_primary.text if ccc_primary else "God never ceases to draw the human heart to himself."} Alongside {ccc_ref_2}, the Church reminds us that our small movement toward prayer is always a response to a God who is already looking toward us with mercy.

### 5. One Question to Carry & A Short Prayer
- **Question to sit with:** *Where in your day today might you feel like you're standing "outside the crowd" looking in—and what would it look like to let Jesus speak directly to that place?*
- **Short Prayer:** *Lord, you know the noise and weight I walked in with today. Quiet my heart enough to hear one word from you, and give me the grace to take the next small step in trust. Amen.*"""


def build_preview_checkin_reflection(
    user_note: str,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
) -> str:
    """Build a deterministic, citation-grounded preview check-in response when demo mode is active."""
    gospel = next(
        (r for r in day.readings if "gospel" in r.label.lower()),
        day.readings[0] if day.readings else None,
    )
    ccc_primary = ccc_hits[0] if ccc_hits else None
    gospel_ref = f"[{gospel.label}] ({gospel.citation})" if gospel else "[Gospel]"
    ccc_ref = f"[{ccc_primary.citation}]" if ccc_primary else "[CCC §2729]"

    return f"""### Sitting With What You Shared
Thank you for naming that honestly: *"{user_note.strip()}"*. Before trying to fix or spiritualize it, it's worth simply acknowledging how tiring it is to carry that weight. You don't have to pretend everything is fine when you come before God.

### How Today's Liturgy Meets You Here
In today's {gospel_ref}, people are standing outside the crowd trying to reach Jesus. You might notice a quiet parallel with what you're carrying today—when life feels overwhelming or prayer feels thin, it's easy to feel like you're on the outside looking in. Yet Jesus stretches out his hand toward those right in front of him, meeting imperfect disciples before they have everything sorted out.

### Catechism Grounding
The Church speaks directly to this human reality in {ccc_ref} (*{ccc_primary.section if ccc_primary else "Prayer and Grace"}*):
> {ccc_primary.text if ccc_primary else "Even in dryness or struggle, faith clings quietly to Christ."}

Notice that the Church doesn't treat struggle as proof that God has left; she treats honest perseverance as a real place of encounter.

### Two Questions to Sit With
1. *If you didn't have to solve this whole burden today, what is the single heaviest part of it that you want to hand over to Christ right now?*
2. *What is one small, gentle boundary or act of honesty that would honor the grace God is offering you today?*

### A Quiet Prayer & Next Step
*Lord Jesus, you see what I am carrying today without me needing to dress it up. Stay close to me in the middle of this, and show me one small way to rest in your mercy today. Amen.*

*(If this weight has been lingering for a while, consider bringing it to a trusted priest in Confession or spiritual direction, or talking it through with a counselor who can walk alongside you.)*"""


def build_examen_prompt(
    *,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    gratitude: str,
    consolation: str,
    desolation: str,
    memory_context: str = "",
) -> str:
    """Build the evening Ignatian Examen prompt tied to the morning's readings and season memory."""
    return f"""Guide the user through a 3-minute evening Ignatian Examen closing out today's liturgical day.

=== USER'S EVENING EXAMEN NOTES ===
- Gratitude (what they are thankful for today): "{gratitude.strip() or 'Not specified'}"
- Consolation (where God felt close or where they responded with love): "{consolation.strip() or 'Not specified'}"
- Desolation / Resistance (where they felt drained, reactive, or pulled away): "{desolation.strip() or 'Not specified'}"

=== SEASON CONTINUITY (OPT-IN MEMORY) ===
{memory_context or "No prior saved entries."}

=== TODAY'S LITURGICAL CONTEXT ===
{_format_liturgy_context(day)}

=== RETRIEVED CATECHISM PARAGRAPHS ===
{_format_ccc_context(ccc_hits)}

Write a calm, unhurried evening Examen reflection using these exact markdown headings:

### 1. Gathering the Day in Gratitude & Consolation
Reflect warmly on the gratitude and consolation they named, connecting it to how God was quietly present in their ordinary hours today.

### 2. Sitting Gently With the Hard Moment (Desolation)
Look at the place where they felt drained, reactive, or distant—without scolding. Help them notice what was underneath that reaction (fear, fatigue, pride, hurt). If their season memory shows a recurring pattern, name it with kindness.

### 3. Evening Mirror of Today's Word & Catechism
Show how today's readings ([First Reading], [Responsorial Psalm], [Gospel]) or [Saint] and 1–2 retrieved [CCC §N] paragraphs speak mercy and perspective over how the day actually unfolded.

### 4. Releasing the Day & Tomorrow's Grace
Offer one gentle intention for tomorrow and a short 2–3 sentence night prayer (in the quiet spirit of Compline)."""


def build_preview_examen_reflection(
    *,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    gratitude: str,
    consolation: str,
    desolation: str,
    memory_context: str = "",
) -> str:
    """Deterministic, citation-grounded preview for the 3-minute Evening Ignatian Examen."""
    gospel = next(
        (r for r in day.readings if "gospel" in r.label.lower()),
        day.readings[0] if day.readings else None,
    )
    ccc_primary = ccc_hits[0] if ccc_hits else None
    gospel_ref = f"[{gospel.label}] ({gospel.citation})" if gospel else "[Gospel]"
    ccc_ref = f"[{ccc_primary.citation}]" if ccc_primary else "[CCC §2560]"

    return f"""### 1. Gathering the Day in Gratitude & Consolation
As the day settles, we begin where St. Ignatius always begins—not with a scorecard of faults, but with gratitude. You named: *"{gratitude.strip() or 'the quiet gifts of making it through today'}"*, and noticed closeness to God in: *"{consolation.strip() or 'small moments of patience and honesty'}"*. Those aren't accidents; they are real traces of grace in the middle of your week.

### 2. Sitting Gently With the Hard Moment (Desolation)
You also named where things felt heavy or where you pulled away: *"{desolation.strip() or 'moments of fatigue, distraction, or impatience'}"*. Instead of judging yourself harshly tonight, notice what was underneath that friction. Often our sharpest reactions or our impulse to shut down happen right where we feel most stretched or unguarded.

### 3. Evening Mirror of Today's Word & Catechism
Look back at this morning's {gospel_ref} alongside {ccc_ref} (*{ccc_primary.section if ccc_primary else "God First Calls Us in Prayer"}*):
> {ccc_primary.text if ccc_primary else "Prayer is the encounter of God's thirst with ours."}

Even the messy or unfinished hours of today belong to Christ when you hand them back to him honestly at night.

### 4. Releasing the Day & Tomorrow's Grace
- **One Intention for Tomorrow:** *When that familiar tension returns tomorrow, pause for one slow breath before answering and remember you are already within Christ's household.*
- **Night Prayer:** *Protect us, Lord, while we stay awake, and watch over us while we sleep, that awake we may keep watch with Christ, and asleep, rest in his peace. Amen.*"""


def build_confession_prep_prompt(
    *,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    focus_area: str,
    memory_context: str,
) -> str:
    """Build a non-scrupulous Catholic Confession preparation prompt grounded in CCC and season memory."""
    return f"""Help a Catholic user prepare prayerfully and honestly for the Sacrament of Penance and Reconciliation (Confession) with a priest.

=== USER'S CURRENT BURDEN / FOCUS ===
"{focus_area.strip() or 'Help me examine my patterns honestly before Confession.'}"

=== SEASON CONTINUITY (RECENT SAVED REFLECTIONS & THEMES) ===
{memory_context}

=== TODAY'S LITURGICAL CONTEXT ===
{_format_liturgy_context(day)}

=== RETRIEVED CATECHISM PARAGRAPHS ===
{_format_ccc_context(ccc_hits)}

Write a gentle, grounded Catholic preparation guide using these exact markdown headings:

### 1. Approaching Mercy Without Fear (Distinguishing Sin From Fatigue)
Anchor the user in the Church's teaching on interior repentance and mercy (citing retrieved [CCC §N] paragraphs such as [CCC §1422], [CCC §1431], [CCC §1441], or [CCC §1776] when present in context). Crucially, help them distinguish between **genuine moral choices** (where we knowingly turn away from love of God or neighbor) and **human limitation** (burnout, anxiety, involuntary distraction, or emotional exhaustion), so they don't carry false scrupulosity into the confessional.

### 2. Gentle Examination of Conscience (Questions to Sit With)
Offer 4–5 clear, non-judgmental examination questions tailored to what they shared and their recurring season themes—grouped across love of God, love of neighbor, and honesty with oneself.

### 3. Practical Guide: What to Bring to the Priest
Give a simple, calm checklist they can bring into the confessional:
- How to begin ("Bless me, Father, for I have sinned...")
- 2–3 plain-language ways to name the root patterns they've been noticing
- A classic **Act of Contrition**
Remind them clearly that this companion is only a preparation aid—sacramental absolution comes through the ministry of the priest in Confession."""


def build_preview_confession_prep_reflection(
    *,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    focus_area: str,
    memory_context: str,
) -> str:
    """Deterministic, citation-grounded preview for Confession Preparation."""
    ccc_refs = [f"[{h.citation}]" for h in ccc_hits[:3]] or ["[CCC §1431]", "[CCC §1422]", "[CCC §1776]"]
    primary_hit = ccc_hits[0] if ccc_hits else None

    return f"""### 1. Approaching Mercy Without Fear (Distinguishing Sin From Fatigue)
As you prepare to bring *"{focus_area.strip() or 'your recent weeks and patterns'}"* to the Sacrament of Reconciliation, start by remembering who meets you in the confessional. As the Catechism teaches in {", ".join(ccc_refs)}:
> {primary_hit.text if primary_hit else "Interior repentance is a radical reorientation of our whole life, a return, a conversion to God with all our heart."}

Before listing faults, it helps to separate **human exhaustion or anxiety** from **deliberate choices against love**. Feeling tired, overwhelmed, or emotionally dry in prayer is not a sin—it is part of being human. Confession is for the places where we chose resentment over mercy, dishonesty over truth, or closed our hearts to God and the people around us.

### 2. Gentle Examination of Conscience (Questions to Sit With)
Drawing on what you shared and your recent season reflections, sit quietly with these questions:
1. **Before God:** *When prayer felt dry or life felt busy, did I give up on turning to God honestly, or try to carry everything on my own terms?*
2. **With Others:** *Where did fatigue or frustration spill over into impatience, harsh words, holding a grudge, or withholding kindness from family or coworkers?*
3. **Within Myself:** *Have I been nursing resentment, numbing out instead of resting well, or hiding behind pride instead of asking for help?*
4. **Patterns Across This Season:** *Looking at your recent reflections ({memory_context.splitlines()[1] if len(memory_context.splitlines()) > 1 else "your daily check-ins"}), what is the one root habit asking most for Christ's healing right now?*

### 3. Practical Guide: What to Bring to the Priest
- **How to Begin:** *"Bless me, Father, for I have sinned. It has been [time] since my last Confession."*
- **Naming Your Heart Plainly:** You don't need fancy theological words. Simply name the concrete choices and patterns on your conscience (and roughly how often), then listen to the priest's counsel.
- **Act of Contrition:**
  > *My God, I am sorry for my sins with all my heart. In choosing to do wrong and failing to do good, I have sinned against you whom I should love above all things. I firmly intend, with your help, to do penance, to sin no more, and to avoid whatever leads me to sin. Our Savior Jesus Christ suffered and died for us. In his name, my God, have mercy. Amen.*

*(Note: This tool helps you prepare your heart; sacramental forgiveness is received in person from a Catholic priest in the Sacrament of Reconciliation. Once you go to Confession, you can click **"Wipe Memory (Clean Slate)"** above to clear your saved notes.)*"""


def build_lectio_divina_prompt(
    *,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    selected_phrase: str = "",
) -> str:
    """Build a 4-step monastic Lectio Divina prompt anchored to today's Gospel."""
    phrase_line = (
        f'The user was especially drawn to this phrase: "{selected_phrase.strip()}"'
        if selected_phrase.strip()
        else "The user has not picked a specific phrase yet—choose one vivid, short phrase from today's Gospel to linger on."
    )
    return f"""Guide the user through a calm, unhurried 4-step Catholic Lectio Divina anchored in today's Gospel and Catechism.

=== USER FOCUS ===
{phrase_line}

=== TODAY'S LITURGICAL CONTEXT ===
{_format_liturgy_context(day)}

=== RETRIEVED CATECHISM PARAGRAPHS ===
{_format_ccc_context(ccc_hits)}

Write the guided prayer using these exact markdown headings:

### 1. Lectio (Reading — Hearing the Word Slowly)
Introduce today's [Gospel] scene gently in 2–3 plain sentences and quote one short focal phrase to read slowly twice.

### 2. Meditatio (Meditation — Sitting With the Phrase)
Invite the reader to notice what stirs inside them around that phrase—curiosity, comfort, or quiet resistance—and connect 1 retrieved [CCC §N] paragraph in warm, everyday language.

### 3. Oratio (Prayer — Speaking Honestly to God)
Offer a brief, honest 2–3 sentence prayer response (without religious clichés) and one open prompt for what they might say to Christ in their own words.

### 4. Contemplatio (Contemplation — Resting in Stillness)
Invite the reader to set down words and rest in silent presence before God (citing [CCC §2709] if present in context, otherwise referencing quiet attentive prayer) for 1–5 minutes using the stillness timer."""


def build_preview_lectio_divina(
    *,
    day: LiturgicalDay,
    ccc_hits: list[CatechismHit],
    selected_phrase: str = "",
) -> str:
    """Deterministic, citation-grounded preview for guided Lectio Divina."""
    gospel = next(
        (r for r in day.readings if "gospel" in r.label.lower()),
        day.readings[0] if day.readings else None,
    )
    gospel_ref = f"[{gospel.label}] ({gospel.citation})" if gospel else "[Gospel]"
    ccc_primary = ccc_hits[0] if ccc_hits else None
    ccc_ref = f"[{ccc_primary.citation}]" if ccc_primary else "[CCC §2709]"
    phrase = selected_phrase.strip() or "Here are my mother and my brothers."

    return f"""### 1. Lectio (Reading — Hearing the Word Slowly)
Pause for one unhurried breath before today's {gospel_ref}. Read this short phrase twice, slowly, as if hearing it for the first time:
> *"{phrase}"*

Notice the tone of Jesus' voice here—not hurried, not distant, but turning directly toward the people right in front of him.

### 2. Meditatio (Meditation — Sitting With the Phrase)
Stay with that single line without rushing to analyze it. Notice whether it brings relief, longing, or a quiet ache of feeling on the outside. The Catechism frames this attentive listening in {ccc_ref} (*{ccc_primary.section if ccc_primary else "Contemplative Prayer"}*):
> {ccc_primary.text if ccc_primary else "Contemplative prayer is a gaze of faith fixed on Jesus, an attentiveness to the Word of God, a silent love."}

### 3. Oratio (Prayer — Speaking Honestly to God)
Let whatever surfaced in your heart become a simple, unfiltered sentence to Christ:
- *Prompt:* Tell Jesus honestly what feels hardest to trust him with right now.
- *Prayer:* *Lord Jesus, I don't have polished words today. Meet me where I actually am, and let your Word settle deeper than my worries. Amen.*

### 4. Contemplatio (Contemplation — Resting in Stillness)
Now set down even your thoughts and questions. Start the **Quiet Contemplation Timer** below (1, 3, or 5 minutes) and simply rest in God's presence, knowing he looks at you with love."""




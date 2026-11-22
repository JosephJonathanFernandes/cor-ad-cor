"""Spoken-word script cleaner and calm neural MP3 voice-note synthesizer."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Awaitable, Callable

SynthesizerFn = Callable[[str, str, str, Path], Awaitable[Path]]

_CCC_TAG_RE = re.compile(r"\[CCC\s*§?\s*(\d+)\]", re.I)
_SCRIPTURE_TAG_RE = re.compile(
    r"\[(First Reading|Reading 1|Second Reading|Reading 2|Responsorial Psalm|Psalm|Gospel|Saint)\]",
    re.I,
)
_HEADING_RE = re.compile(r"^#{1,6}\s*(?:\d+\.\s*)?", re.M)
_MARKDOWN_DECOR_RE = re.compile(r"(\*\*|\*|__|`|>\s?)")


def prepare_spoken_script(markdown_text: str) -> str:
    """Convert a markdown companion reflection into natural, unhurried spoken prose."""
    text = markdown_text.strip()
    if not text:
        return ""

    text = _CCC_TAG_RE.sub(r"Catechism paragraph \1", text)
    text = _SCRIPTURE_TAG_RE.sub(
        lambda m: f"the {m.group(1)}" if m.group(1).lower() != "saint" else "today's saint",
        text,
    )
    text = _HEADING_RE.sub("", text)
    text = _MARKDOWN_DECOR_RE.sub("", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def estimate_duration_seconds(spoken_script: str, words_per_minute: int = 135) -> int:
    """Estimate calm spoken duration in seconds (default 135 WPM unhurried pace)."""
    words = len(spoken_script.split())
    if words == 0:
        return 0
    return max(1, round((words / words_per_minute) * 60))


async def _default_edge_tts_synthesize(
    spoken_text: str,
    voice: str,
    rate: str,
    output_path: Path,
) -> Path:
    try:
        import edge_tts
    except ImportError as exc:
        raise RuntimeError(
            "edge-tts is not installed. Run `.venv\\Scripts\\pip install edge-tts` to enable MP3 voice-notes."
        ) from exc

    communicate = edge_tts.Communicate(text=spoken_text, voice=voice, rate=rate)
    await communicate.save(str(output_path))
    return output_path


class VoiceNoteSynthesizer:
    """Synthesizes and caches calm MP3 voice-notes from companion reflections."""

    def __init__(
        self,
        *,
        cache_dir: Path,
        voice: str = "en-US-AndrewMultilingualNeural",
        rate: str = "-6%",
        synthesizer: SynthesizerFn | None = None,
    ) -> None:
        self.cache_dir = cache_dir
        self.voice = voice
        self.rate = rate
        self._synthesizer = synthesizer or _default_edge_tts_synthesize

    async def synthesize_mp3(self, markdown_text: str, *, voice: str | None = None) -> tuple[Path, str]:
        """Return (mp3_path, spoken_script), reusing a cached MP3 when identical."""
        spoken = prepare_spoken_script(markdown_text)
        if not spoken:
            raise ValueError("Cannot synthesize audio from empty reflection text.")

        chosen_voice = (voice or self.voice).strip() or self.voice
        cache_key = hashlib.sha256(f"{chosen_voice}|{self.rate}|{spoken}".encode("utf-8")).hexdigest()[:20]
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.cache_dir / f"voice_{cache_key}.mp3"

        if not out_path.exists() or out_path.stat().st_size == 0:
            await self._synthesizer(spoken, chosen_voice, self.rate, out_path)

        return out_path, spoken

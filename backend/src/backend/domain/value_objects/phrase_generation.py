from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhraseGeneration:
    """What was made for a phrase.

    `polish`: a polished phrase, shown or reverted; `text_media`: TTS or a video frame or
    clip with its file. Both are made of the phrase's exact text. `meaning` explains the
    target where the phrase stands, whatever the cut.
    """

    polish: bool = False
    meaning: bool = False
    text_media: bool = False
    cloze: bool = False

    @property
    def any(self) -> bool:
        return self.polish or self.meaning or self.text_media or self.cloze

    @property
    def of_text(self) -> bool:
        """Made of the exact text: lost when the phrase is cut again."""
        return self.polish or self.text_media


NO_GENERATION = PhraseGeneration()

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.inflected_forms import is_inflected_form
from backend.domain.value_objects.frequency_band import FrequencyBand
from backend.domain.value_objects.frequent_word_threshold import is_frequent

if TYPE_CHECKING:
    from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
    from backend.domain.value_objects.cefr_level import CEFRLevel

type _ReviewKey = tuple[bool, int, float, float, str]

_MIN_WORD_LENGTH = 2


class ReviewOrderWordSelector:
    """Selects calibration words the way Review would suggest them.

    A lemma stands at its easiest CEFR level, the one its common use has, and counts if that
    level is the user's or harder: `try` (A1 verb, B2 noun) is not asked at B2. Single letters
    and inflected forms (`playing`, `known`) are skipped: Review only has their bases. Order as in
    Review: frequent words (probably known) last, then more frequent bands first, easier
    levels first, more frequent words first.
    """

    def select_words(
        self,
        entries: list[BootstrapWordEntry],
        user_level: CEFRLevel,
        frequent_zipf: float | None,
        decided_lemmas: set[str],
        excluded_lemmas: set[str],
        limit: int,
        dictionary_lemmas: set[str] | None = None,
    ) -> list[BootstrapWordEntry]:
        """`dictionary_lemmas`: every word of the dictionaries, the bases of inflected forms
        among them; the entries' own lemmas if not given."""
        easiest: dict[str, BootstrapWordEntry] = {}
        for entry in entries:
            current = easiest.get(entry.lemma)
            if current is None or entry.cefr_level.value < current.cefr_level.value:
                easiest[entry.lemma] = entry
        lemmas = set(easiest) if dictionary_lemmas is None else dictionary_lemmas | set(easiest)
        words = [
            word for word in easiest.values()
            if word.cefr_level.is_learned_at(user_level)
            and len(word.lemma) >= _MIN_WORD_LENGTH
            and not is_inflected_form(word.lemma, lemmas)
            and word.lemma not in decided_lemmas
            and word.lemma not in excluded_lemmas
        ]

        def review_key(word: BootstrapWordEntry) -> _ReviewKey:
            return (
                is_frequent(word.zipf_value, frequent_zipf),
                -FrequencyBand.from_zipf(word.zipf_value).value,
                word.cefr_level.value,
                -word.zipf_value,
                word.lemma,
            )

        return sorted(words, key=review_key)[:limit]

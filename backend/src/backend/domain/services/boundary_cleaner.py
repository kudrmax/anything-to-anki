from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData

# Minimum content words to keep after cleanup. Mirrors FragmentExtractor.MIN_FRAGMENT_WORDS.
MIN_FRAGMENT_CONTENT_WORDS: int = 5

# POS tags that may be stripped from the LEFT edge.
_LEFT_STRIP_POS = frozenset({"CCONJ", "SCONJ"})

# POS tags that may be stripped from the RIGHT edge.
# DET / ADP / PRON / PART have additional conditions checked in code.
# INTJ at right edge ("please", "yeah", "oh") is almost always a discourse tail.
_RIGHT_STRIP_POS = frozenset({"CCONJ", "SCONJ", "DET", "INTJ"})

# AUX dependency labels that mean "auxiliary helping a verb that's not in the
# fragment" — these are dangling helpers like trailing "have" in "...to have".
_AUX_DEPS = frozenset({"aux", "auxpass"})

# Subject pronouns that look incomplete when dangling at the right edge.
_RIGHT_STRIP_PRON_LEMMAS = frozenset(
    {"i", "you", "he", "she", "it", "we", "they"}
)

# Dependency labels that mean "subject of a verb" — only these PRON cases
# qualify for right-edge stripping (object pronouns like "with you" stay).
_SUBJECT_DEPS = frozenset({"nsubj", "nsubjpass"})

# Words that often act as relativizers/complementizers at the start of a fragment.
_LEFT_STRIP_RELATIVIZERS = frozenset({"that", "which", "who", "whom", "whose"})

# Sentence-final punctuation that should NOT be stripped from the right.
_KEEP_RIGHT_PUNCT = frozenset({".", "!", "?"})


class BoundaryCleaner:
    """Trims dangling function words from the edges of a fragment.

    Pure trim — never extends. Operates on a sorted list of token indices and
    returns a new sorted list with the edges cleaned.

    Stops if cleaning would:
    - drop the fragment below MIN_FRAGMENT_CONTENT_WORDS content words, or
    - remove a token marked as protected (typically the target).
    """

    def clean(
        self,
        tokens: list[TokenData],
        indices: list[int],
        protected_indices: frozenset[int] = frozenset(),
    ) -> list[int]:
        if not indices:
            return list(indices)

        result = sorted(set(indices))

        # Trim left until stable.
        while result and self._should_strip_left(tokens, result, protected_indices):
            result = result[1:]

        # Trim right until stable.
        while result and self._should_strip_right(tokens, result, protected_indices):
            result = result[:-1]

        return result

    # ------------------------------------------------------------------ left

    def _should_strip_left(
        self,
        tokens: list[TokenData],
        indices: list[int],
        protected: frozenset[int],
    ) -> bool:
        first_idx = indices[0]
        if first_idx in protected:
            return False

        token = tokens[first_idx]

        if token.is_punct:
            return self._meets_min_after(tokens, indices[1:])

        if token.pos in _LEFT_STRIP_POS:
            return self._meets_min_after(tokens, indices[1:])

        # Relativizers / complementizers ("that", "which", "who", ...).
        # Skip if the next token is a noun — then it's a demonstrative determiner
        # like "that man" / "which book" and shouldn't be stripped.
        if token.lemma.lower() in _LEFT_STRIP_RELATIVIZERS and token.pos in {
            "PRON",
            "SCONJ",
            "DET",
            "ADV",  # spaCy sometimes tags relative "where"/"when" as ADV
        }:
            if len(indices) >= 2:
                next_token = tokens[indices[1]]
                if next_token.pos in {"NOUN", "PROPN"}:
                    return False
            return self._meets_min_after(tokens, indices[1:])

        return False

    # ----------------------------------------------------------------- right

    def _should_strip_right(
        self,
        tokens: list[TokenData],
        indices: list[int],
        protected: frozenset[int],
    ) -> bool:
        last_idx = indices[-1]
        if last_idx in protected:
            return False

        token = tokens[last_idx]

        # Trailing punctuation, except sentence-final . ! ?
        if token.is_punct:
            if token.text in _KEEP_RIGHT_PUNCT:
                return False
            return self._meets_min_after(tokens, indices[:-1])

        if token.pos in _RIGHT_STRIP_POS:
            return self._meets_min_after(tokens, indices[:-1])

        # Adposition with no object inside the fragment is dangling.
        if token.pos == "ADP":
            has_object_inside = any(
                child in indices for child in token.children_indices
            )
            if not has_object_inside:
                return self._meets_min_after(tokens, indices[:-1])
            return False

        # Subject pronouns at the right edge with their verb missing.
        # Only strip if it's truly a dangling subject (dep=nsubj/nsubjpass) AND
        # its verb head is not in the fragment. This protects object pronouns
        # such as "with you" where 'you' is pobj of 'with'.
        if (
            token.pos == "PRON"
            and token.lemma.lower() in _RIGHT_STRIP_PRON_LEMMAS
            and token.dep in _SUBJECT_DEPS
            and token.head_index not in indices
        ):
            return self._meets_min_after(tokens, indices[:-1])

        # Relative / demonstrative pronouns dangling at right ("...i.e., that")
        if token.pos == "PRON" and token.lemma.lower() in _LEFT_STRIP_RELATIVIZERS:
            return self._meets_min_after(tokens, indices[:-1])

        # Possessive pronouns dangling at right ("...hit its") — they expect
        # a noun that isn't in the fragment.
        if token.pos == "PRON" and token.tag == "PRP$":
            return self._meets_min_after(tokens, indices[:-1])

        # Auxiliary verb / infinitive marker whose main verb is outside the
        # fragment ("...considered to have").
        if token.pos in {"AUX", "PART"} and token.dep in _AUX_DEPS:
            if token.head_index not in indices:
                return self._meets_min_after(tokens, indices[:-1])
            return False

        return False

    # ----------------------------------------------------------------- utils

    @staticmethod
    def _meets_min_after(tokens: list[TokenData], remaining: list[int]) -> bool:
        content = sum(
            1
            for idx in remaining
            if tokens[idx].is_alpha and not tokens[idx].is_punct
        )
        return content >= MIN_FRAGMENT_CONTENT_WORDS

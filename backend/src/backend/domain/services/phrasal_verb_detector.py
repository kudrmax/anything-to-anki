from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.phrasal_verb_dictionary import PhrasalVerbDictionary

_PARTICLE_DEPS = frozenset({"prt"})
_PREP_DEPS = frozenset({"prep"})


@dataclass(frozen=True)
class PhrasalVerbMatch:
    """A detected phrasal verb with its component token indices."""

    verb_index: int
    particle_index: int
    lemma: str         # e.g. "give up", "look after"
    surface_form: str  # e.g. "gave up", "looked after" — actual form in text


class PhrasalVerbDetector:
    """Detects phrasal verbs using two-layer approach:

    Layer 1 (dep=prt): VERB + particle child — reliable spaCy detection, no dictionary needed.
    Layer 2 (dep=prep): VERB + prep child — checked against phrasal verb dictionary.
    """

    def __init__(self, dictionary: PhrasalVerbDictionary) -> None:
        self._dictionary = dictionary

    def detect(self, tokens: list[TokenData]) -> list[PhrasalVerbMatch]:
        """Return all phrasal verb matches found in the token list."""
        token_map = {t.index: t for t in tokens}
        matches: list[PhrasalVerbMatch] = []

        for token in tokens:
            if token.pos != "VERB":
                continue

            for child_idx in token.children_indices:
                child = token_map.get(child_idx)
                if child is None:
                    continue

                if child.dep in _PARTICLE_DEPS:
                    # Layer 1: always a phrasal verb
                    matches.append(
                        PhrasalVerbMatch(
                            verb_index=token.index,
                            particle_index=child.index,
                            lemma=f"{token.lemma.lower()} {child.text.lower()}",
                            surface_form=f"{token.text} {child.text}",
                        )
                    )
                elif (
                    child.dep in _PREP_DEPS
                    and child.is_alpha
                    and self._dictionary.contains(token.lemma, child.text)
                ):
                    # Layer 2: dictionary confirms the phrasal verb
                    matches.append(
                        PhrasalVerbMatch(
                            verb_index=token.index,
                            particle_index=child.index,
                            lemma=f"{token.lemma.lower()} {child.text.lower()}",
                            surface_form=f"{token.text} {child.text}",
                        )
                    )

        return matches

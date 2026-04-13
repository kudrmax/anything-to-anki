from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.ports.phrasal_verb_dictionary import PhrasalVerbDictionary

_PARTICLE_DEPS = frozenset({"prt"})
_PREP_DEPS = frozenset({"prep"})
_DOBJ_DEPS = frozenset({"dobj", "attr", "oprd"})


def _is_better(
    candidate: PhrasalVerbMatch,
    current: PhrasalVerbMatch | None,
) -> bool:
    """Return True if candidate has more components than current best."""
    if current is None:
        return True
    return len(candidate.component_indices) > len(current.component_indices)


@dataclass(frozen=True)
class PhrasalVerbMatch:
    """A detected phrasal verb with its component token indices."""

    verb_index: int
    component_indices: tuple[int, ...]  # all token indices forming the PV (verb + particles/nouns)
    lemma: str         # e.g. "give up", "go through with", "make fun of"
    surface_form: str  # e.g. "gave up", "going through with" — actual form in text


class PhrasalVerbDetector:
    """Detects phrasal verbs using a multi-layer approach:

    Layer 1 (dep=prt): VERB + particle child — reliable spaCy detection, no dictionary needed.
    Layer 2 (dep=prep): VERB + prep child — checked against phrasal verb dictionary.
    Layer 2b (prep chain): VERB + prep + prep — 3-word phrasal verbs via dictionary.
    Layer 3 (VERB+NOUN+PREP): VERB + dobj(NOUN) + prep — idiomatic expressions via dictionary.
    """

    def __init__(self, dictionary: PhrasalVerbDictionary) -> None:
        self._dictionary = dictionary

    def detect(self, tokens: list[TokenData]) -> list[PhrasalVerbMatch]:
        """Return all phrasal verb matches found in the token list."""
        token_map = {t.index: t for t in tokens}
        matches: list[PhrasalVerbMatch] = []
        matched_verb_indices: set[int] = set()

        for token in tokens:
            if token.pos != "VERB":
                continue

            best: PhrasalVerbMatch | None = None

            # Collect children by role
            prt_children: list[TokenData] = []
            prep_children: list[TokenData] = []
            dobj_noun_children: list[TokenData] = []

            for child_idx in token.children_indices:
                child = token_map.get(child_idx)
                if child is None:
                    continue
                if child.dep in _PARTICLE_DEPS:
                    prt_children.append(child)
                elif child.dep in _PREP_DEPS and child.is_alpha:
                    prep_children.append(child)
                elif child.dep in _DOBJ_DEPS and child.pos == "NOUN":
                    dobj_noun_children.append(child)

            # --- Layer 1: VERB + prt (always valid, no dictionary) ---
            for prt in prt_children:
                match = PhrasalVerbMatch(
                    verb_index=token.index,
                    component_indices=(prt.index,),
                    lemma=f"{token.lemma.lower()} {prt.text.lower()}",
                    surface_form=self._build_surface(token_map, token.index, prt.index),
                )
                if _is_better(match, best):
                    best = match

            # --- Layer 2b: VERB + prep + prep chain (3-word, dictionary) ---
            # Try 3-word combinations BEFORE 2-word to prefer longer matches.
            for prep in prep_children:
                # Check prep's own prep children (grandchildren of verb)
                for gc_idx in prep.children_indices:
                    gc = token_map.get(gc_idx)
                    if gc is None or gc.dep not in _PREP_DEPS or not gc.is_alpha:
                        continue
                    phrase = f"{token.lemma.lower()} {prep.text.lower()} {gc.text.lower()}"
                    if self._dictionary.contains_phrase(phrase):
                        match = PhrasalVerbMatch(
                            verb_index=token.index,
                            component_indices=(prep.index, gc.index),
                            lemma=phrase,
                            surface_form=self._build_surface(token_map, token.index, gc.index),
                        )
                        if _is_better(match, best):
                            best = match

                # Also check pairs of direct prep children (both are children of verb)
                for prep2 in prep_children:
                    if prep2.index <= prep.index:
                        continue
                    phrase = f"{token.lemma.lower()} {prep.text.lower()} {prep2.text.lower()}"
                    if self._dictionary.contains_phrase(phrase):
                        match = PhrasalVerbMatch(
                            verb_index=token.index,
                            component_indices=(prep.index, prep2.index),
                            lemma=phrase,
                            surface_form=self._build_surface(token_map, token.index, prep2.index),
                        )
                        if _is_better(match, best):
                            best = match

            # --- Layer 2: VERB + prep (2-word, dictionary) ---
            # Only if no longer match was found above.
            if best is None or len(best.component_indices) < 2:
                for prep in prep_children:
                    if self._dictionary.contains(token.lemma, prep.text):
                        match = PhrasalVerbMatch(
                            verb_index=token.index,
                            component_indices=(prep.index,),
                            lemma=f"{token.lemma.lower()} {prep.text.lower()}",
                            surface_form=self._build_surface(token_map, token.index, prep.index),
                        )
                        if best is None:
                            best = match
                        break  # first prep match is enough for 2-word

            # --- Layer 3: VERB + NOUN(dobj) + PREP (idioms, dictionary) ---
            for noun in dobj_noun_children:
                for gc_idx in noun.children_indices:
                    gc = token_map.get(gc_idx)
                    if gc is None or gc.dep not in _PREP_DEPS or not gc.is_alpha:
                        continue
                    phrase = f"{token.lemma.lower()} {noun.lemma.lower()} {gc.text.lower()}"
                    if self._dictionary.contains_phrase(phrase):
                        match = PhrasalVerbMatch(
                            verb_index=token.index,
                            component_indices=(noun.index, gc.index),
                            lemma=phrase,
                            surface_form=self._build_surface(token_map, token.index, gc.index),
                        )
                        if _is_better(match, best):
                            best = match

            # --- Layer 3b: VERB + NOUN(dobj) + PREP as sibling (both verb children) ---
            # spaCy sometimes attaches prep to verb instead of noun:
            #   made(VERB) → fun(NOUN,dobj), of(ADP,prep)  ← 'of' is verb child
            for noun in dobj_noun_children:
                for prep in prep_children:
                    if prep.index <= noun.index:
                        continue  # prep must follow noun
                    phrase = f"{token.lemma.lower()} {noun.lemma.lower()} {prep.text.lower()}"
                    if self._dictionary.contains_phrase(phrase):
                        match = PhrasalVerbMatch(
                            verb_index=token.index,
                            component_indices=(noun.index, prep.index),
                            lemma=phrase,
                            surface_form=self._build_surface(
                                token_map, token.index, prep.index,
                            ),
                        )
                        if _is_better(match, best):
                            best = match

            if best is not None and token.index not in matched_verb_indices:
                matches.append(best)
                matched_verb_indices.add(token.index)

        return matches

    @staticmethod
    def _build_surface(
        token_map: dict[int, TokenData],
        start_index: int,
        end_index: int,
    ) -> str:
        """Build surface form from all tokens in the span [start_index, end_index]."""
        parts: list[str] = []
        for i in range(start_index, end_index + 1):
            t = token_map.get(i)
            if t is None:
                continue
            parts.append(t.text)
            if i < end_index:
                parts.append(t.whitespace_after or " ")
        return "".join(parts)

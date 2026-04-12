from __future__ import annotations

from backend.domain.entities.token_data import TokenData
from backend.domain.ports.phrasal_verb_dictionary import PhrasalVerbDictionary
from backend.domain.services.phrasal_verb_detector import (
    PhrasalVerbDetector,
)


class FakeDictionary(PhrasalVerbDictionary):
    """In-memory dictionary for tests."""

    def __init__(self, entries: set[str]) -> None:
        self._entries = {e.lower() for e in entries}

    def contains(self, verb_lemma: str, particle: str) -> bool:
        return f"{verb_lemma.lower()} {particle.lower()}" in self._entries

    def contains_phrase(self, phrase: str) -> bool:
        return phrase.lower().strip() in self._entries


def _token(
    index: int,
    text: str,
    lemma: str,
    *,
    pos: str = "NOUN",
    tag: str = "NN",
    dep: str = "",
    head_index: int = 0,
    children_indices: tuple[int, ...] = (),
    whitespace_after: str = " ",
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=lemma,
        pos=pos,
        tag=tag,
        head_index=head_index,
        children_indices=children_indices,
        is_punct=False,
        is_stop=False,
        is_alpha=True,
        is_propn=False,
        sent_index=0,
        dep=dep,
        whitespace_after=whitespace_after,
    )


def _verb(
    index: int,
    text: str,
    lemma: str,
    *,
    children_indices: tuple[int, ...] = (),
) -> TokenData:
    """Shorthand for a VERB token."""
    return _token(
        index, text, lemma,
        pos="VERB", dep="ROOT", head_index=index,
        children_indices=children_indices,
    )


def _prep(
    index: int,
    text: str,
    *,
    head_index: int = 0,
    children_indices: tuple[int, ...] = (),
) -> TokenData:
    """Shorthand for a prep ADP token."""
    return _token(
        index, text, text,
        pos="ADP", dep="prep", head_index=head_index,
        children_indices=children_indices,
    )


def _prt(index: int, text: str, *, head_index: int = 0) -> TokenData:
    """Shorthand for a particle ADP token."""
    return _token(
        index, text, text,
        pos="ADP", dep="prt", head_index=head_index,
    )


class TestLayer1ParticleDetection:
    """Layer 1: VERB + prt — always a phrasal verb."""

    def test_simple_phrasal_verb(self) -> None:
        tokens = [
            _token(0, "I", "I", pos="PRON", dep="nsubj", head_index=1),
            _verb(1, "give", "give", children_indices=(0, 2)),
            _prt(2, "up", head_index=1),
        ]
        detector = PhrasalVerbDetector(FakeDictionary(set()))
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "give up"
        assert matches[0].surface_form == "give up"
        assert matches[0].verb_index == 1
        assert matches[0].component_indices == (2,)

    def test_separable_phrasal_verb_surface_form(self) -> None:
        """surface_form must include intervening tokens."""
        tokens = [
            _token(0, "I", "I", pos="PRON", dep="nsubj", head_index=1),
            _verb(1, "get", "get", children_indices=(0, 2, 3)),
            _token(2, "you", "you", pos="PRON", dep="dobj", head_index=1),
            _prt(3, "out", head_index=1),
        ]
        detector = PhrasalVerbDetector(FakeDictionary(set()))
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "get out"
        assert matches[0].surface_form == "get you out"
        assert matches[0].component_indices == (3,)


class TestLayer2PrepDetection:
    """Layer 2: VERB + prep child — dictionary-confirmed."""

    def test_simple_verb_prep(self) -> None:
        tokens = [
            _verb(0, "look", "look", children_indices=(1,)),
            _prep(1, "after"),
        ]
        detector = PhrasalVerbDetector(FakeDictionary({"look after"}))
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "look after"
        assert matches[0].surface_form == "look after"

    def test_prep_not_in_dictionary_skipped(self) -> None:
        tokens = [
            _verb(0, "look", "look", children_indices=(1,)),
            _prep(1, "at"),
        ]
        detector = PhrasalVerbDetector(FakeDictionary(set()))
        matches = detector.detect(tokens)

        assert matches == []


class TestLayer2bPrepChain:
    """Layer 2b: VERB + prep + prep chain — 3-word PVs."""

    def test_three_word_prep_chain_grandchild(self) -> None:
        """Verb → prep child → prep grandchild."""
        tokens = [
            _verb(0, "going", "go", children_indices=(1,)),
            _prep(1, "through", children_indices=(2,)),
            _prep(2, "with", head_index=1, children_indices=(4,)),
            _token(3, "this", "this", pos="DET", dep="det", head_index=4),
            _token(4, "wedding", "wedding", dep="pobj", head_index=2),
        ]
        detector = PhrasalVerbDetector(
            FakeDictionary({"go through with", "go through"}),
        )
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "go through with"
        assert matches[0].surface_form == "going through with"
        assert matches[0].component_indices == (1, 2)

    def test_three_word_preferred_over_two_word(self) -> None:
        tokens = [
            _verb(0, "going", "go", children_indices=(1,)),
            _prep(1, "through", children_indices=(2,)),
            _prep(2, "with", head_index=1),
        ]
        detector = PhrasalVerbDetector(
            FakeDictionary({"go through", "go through with"}),
        )
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "go through with"

    def test_two_direct_prep_children(self) -> None:
        """Both preps are direct children of verb."""
        tokens = [
            _verb(0, "going", "go", children_indices=(1, 2)),
            _prep(1, "through"),
            _prep(2, "with"),
        ]
        detector = PhrasalVerbDetector(
            FakeDictionary({"go through with", "go with"}),
        )
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "go through with"

    def test_falls_back_to_two_word_when_three_not_in_dict(self) -> None:
        tokens = [
            _verb(0, "look", "look", children_indices=(1,)),
            _prep(1, "forward", children_indices=(2,)),
            _prep(2, "to", head_index=1),
        ]
        detector = PhrasalVerbDetector(
            FakeDictionary({"look forward to"}),
        )
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "look forward to"


class TestLayer3VerbNounPrep:
    """Layer 3: VERB + NOUN(dobj) + PREP — idioms."""

    def test_make_fun_of(self) -> None:
        tokens = [
            _verb(0, "made", "make", children_indices=(1,)),
            _token(
                1, "fun", "fun",
                pos="NOUN", dep="dobj", head_index=0,
                children_indices=(2,),
            ),
            _prep(2, "of", head_index=1),
            _token(3, "me", "me", pos="PRON", dep="pobj", head_index=2),
        ]
        detector = PhrasalVerbDetector(FakeDictionary({"make fun of"}))
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "make fun of"
        assert matches[0].surface_form == "made fun of"
        assert matches[0].component_indices == (1, 2)

    def test_take_care_of(self) -> None:
        tokens = [
            _verb(0, "take", "take", children_indices=(1,)),
            _token(
                1, "care", "care",
                pos="NOUN", dep="dobj", head_index=0,
                children_indices=(2,),
            ),
            _prep(2, "of", head_index=1),
        ]
        detector = PhrasalVerbDetector(FakeDictionary({"take care of"}))
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "take care of"

    def test_noun_without_prep_not_matched(self) -> None:
        tokens = [
            _verb(0, "make", "make", children_indices=(1,)),
            _token(1, "decision", "decision", pos="NOUN", dep="dobj"),
        ]
        detector = PhrasalVerbDetector(FakeDictionary({"make fun of"}))
        matches = detector.detect(tokens)

        assert matches == []

    def test_verb_noun_prep_not_in_dictionary_skipped(self) -> None:
        tokens = [
            _verb(0, "made", "make", children_indices=(1,)),
            _token(
                1, "fun", "fun",
                pos="NOUN", dep="dobj", head_index=0,
                children_indices=(2,),
            ),
            _prep(2, "of", head_index=1),
        ]
        detector = PhrasalVerbDetector(FakeDictionary(set()))
        matches = detector.detect(tokens)

        assert matches == []


class TestDeduplication:
    """No duplicate/subsumed matches for the same verb."""

    def test_no_duplicate_when_three_word_subsumes_two_word(self) -> None:
        tokens = [
            _verb(0, "going", "go", children_indices=(1, 2)),
            _prep(1, "through"),
            _prep(2, "with"),
        ]
        detector = PhrasalVerbDetector(
            FakeDictionary({"go through", "go with", "go through with"}),
        )
        matches = detector.detect(tokens)

        assert len(matches) == 1
        assert matches[0].lemma == "go through with"

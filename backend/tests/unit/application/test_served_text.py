"""The chunks of text an open review served: which of them a changed card makes it send
again (Stage 7)."""
from __future__ import annotations

from dataclasses import replace

from backend.application.utils.served_text import PlaceKey, ServedText
from backend.domain.services.text_chunks import TextChunk
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.shown_place import ShownPlace

from tests.phrase_support import phrase

SOURCE, OTHER = 1, 2
FIRST, SECOND, THIRD = TextChunk(0, 3), TextChunk(3, 5), TextChunk(5, 9)
TEXT = "He gave up the relentless pursuit"


def _place(phrase_id: int, block: int, target: str = "gave up", **changes: object) -> ShownPlace:
    place = ShownPlace(
        phrase_id=phrase_id, word_id=phrase_id, cefr_level="B2", is_phrasal_verb=False,
        source_phrase=phrase(TEXT, target),
        position=DocumentPosition(block, 0, 0, 0, len(TEXT)),
    )
    return replace(place, **changes)  # type: ignore[arg-type]


GAVE_UP, PURSUIT, LATER = _place(1, 1), _place(2, 1, "pursuit"), _place(3, 6)


def _served() -> ServedText:
    """The first and the last chunk of the source served."""
    text = ServedText()
    text.serve(SOURCE, FIRST, [GAVE_UP, PURSUIT])
    text.serve(SOURCE, THIRD, [LATER])
    return text


def test_the_same_places_touch_nothing() -> None:
    text = _served()

    assert text.touched({(SOURCE, 0): [PURSUIT, GAVE_UP], (SOURCE, 5): [LATER]}) == set()


def test_a_moved_position_touches_its_chunk() -> None:
    moved = replace(GAVE_UP, position=DocumentPosition(1, 0, 3, 0, len(TEXT)))

    assert _served().touched({(SOURCE, 0): [moved, PURSUIT]}) == {(SOURCE, 0)}


def test_a_new_target_touches_its_chunk() -> None:
    assert PlaceKey.of(_place(1, 1, "gave")) != PlaceKey.of(GAVE_UP)
    assert _served().touched({(SOURCE, 0): [_place(1, 1, "gave"), PURSUIT]}) == {(SOURCE, 0)}


def test_a_cefr_change_touches_its_chunk() -> None:
    harder = replace(GAVE_UP, cefr_level="C1")

    assert _served().touched({(SOURCE, 0): [harder, PURSUIT]}) == {(SOURCE, 0)}


def test_a_phrasal_flag_change_touches_its_chunk() -> None:
    phrasal = replace(GAVE_UP, is_phrasal_verb=True)

    assert _served().touched({(SOURCE, 0): [phrasal, PURSUIT]}) == {(SOURCE, 0)}


def test_a_new_card_in_a_served_chunk_is_a_candidate_and_touches_it() -> None:
    text = _served()
    new = _place(4, 2)

    assert text.candidates([(SOURCE, new.position.block)], ()) == {SOURCE: [FIRST]}
    assert text.touched({(SOURCE, 0): [GAVE_UP, PURSUIT, new]}) == {(SOURCE, 0)}


def test_a_card_in_a_chunk_not_served_is_no_candidate() -> None:
    text = _served()

    assert text.candidates([(SOURCE, 4), (OTHER, 1)], ()) == {}
    assert text.chunk_of(SOURCE, 4) is None


def test_a_removed_served_card_touches_its_chunk() -> None:
    """A card whose phrase is not stored any more may have stood in any chunk of its
    source."""
    text = _served()

    assert text.candidates([], [SOURCE, OTHER]) == {SOURCE: [FIRST, THIRD]}
    assert text.touched({(SOURCE, 0): [PURSUIT], (SOURCE, 5): [LATER]}) == {(SOURCE, 0)}


def test_a_card_hidden_by_overlap_that_changes_touches_its_chunk() -> None:
    """`gave` under `gave up` shows no mark of its own, yet whether it shows depends on
    the card over it: the chunk is sent again."""
    hidden = _place(5, 1, "gave")
    text = ServedText()
    text.serve(SOURCE, FIRST, [GAVE_UP, hidden])

    assert text.touched({(SOURCE, 0): [GAVE_UP, replace(hidden, cefr_level="C2")]}) == {
        (SOURCE, 0),
    }


def test_a_chunk_served_again_is_held_as_served_then() -> None:
    text = _served()
    harder = replace(GAVE_UP, cefr_level="C1")
    text.serve(SOURCE, FIRST, [harder, PURSUIT])

    assert text.touched({(SOURCE, 0): [harder, PURSUIT]}) == set()
    assert text.refs() == [(SOURCE, 0), (SOURCE, 5)]


def test_a_forgotten_source_is_never_touched_again() -> None:
    text = _served()
    text.serve(OTHER, FIRST, [GAVE_UP])

    text.forget_source(SOURCE)

    assert text.sources() == frozenset({OTHER})
    assert text.candidates([(SOURCE, 1)], [SOURCE]) == {}
    assert text.touched({(SOURCE, 0): []}) == set()
    assert text.refs() == [(OTHER, 0)]

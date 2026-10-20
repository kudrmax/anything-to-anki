"""ReviewCards: whether a word open in a source is done via another one, read from the one
snapshot of what the user knows that the card view reads too."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_cards import ReviewCards
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.word_status import WordStatus

from tests.card_support import PhraseWordStates, occurrence, word
from tests.decision_support import NOW
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.review_card import ReviewCard

pytestmark = pytest.mark.unit

LEMMA = "glare"
FRESH = (NOW - timedelta(days=1),)
DUE = (NOW - LEARNING_KNOWN_AFTER,)


def _known(*lemmas: str) -> MagicMock:
    repo = MagicMock()
    repo.get_all_pairs.return_value = {(lemma, None) for lemma in lemmas}
    return repo


def _cards(
    vocabulary: UserVocabulary, the_word: StoredCandidate, the_phrase: Occurrence,
) -> ReviewCards:
    candidates = MagicMock()
    candidates.get_by_source.return_value = [the_word]
    candidates.get_by_id.return_value = the_word
    occurrences = MagicMock()
    occurrences.shown_by_word.return_value = {the_word.id: [the_phrase]}
    occurrences.get.return_value = the_phrase
    return ReviewCards(
        candidates, occurrences,
        PhraseWordStates(lambda: [the_word], lambda _word_id: [the_phrase]),
        vocabulary,
    )


def _open_card(vocabulary: UserVocabulary) -> ReviewCard:
    cards = _cards(vocabulary, word(1, LEMMA), occurrence(1, 1))
    [found] = cards.of_sources([10])
    assert cards.of_phrase(1) == found, "one card, however it is read"
    return found


@pytest.mark.parametrize(
    ("vocabulary", "elsewhere", "pressed", "shown"),
    [
        pytest.param(
            user_vocabulary(learning_lemmas={LEMMA}), ElsewhereStatus.LEARN,
            Press.LEARN, WordStatus.LEARN, id="learn-waiting-for-export",
        ),
        pytest.param(
            user_vocabulary(active_since={LEMMA: FRESH}), ElsewhereStatus.LEARNING,
            Press.LEARN, WordStatus.LEARNING, id="in-anki",
        ),
        pytest.param(
            user_vocabulary(active_since={LEMMA: DUE}), ElsewhereStatus.KNOWN,
            Press.KNOWN, WordStatus.KNOWN, id="known-by-timer",
        ),
        pytest.param(
            user_vocabulary(_known(LEMMA)), ElsewhereStatus.KNOWN,
            Press.KNOWN, WordStatus.KNOWN, id="known-by-list",
        ),
    ],
)
def test_a_word_open_here_is_done_by_what_another_source_holds(
    vocabulary: UserVocabulary, elsewhere: ElsewhereStatus, pressed: Press, shown: WordStatus,
) -> None:
    card = _open_card(vocabulary)

    assert card.elsewhere is elsewhere
    assert [b.button for b in card.view.buttons if b.pressed] == [pressed]
    assert all(b.command is None for b in card.view.buttons)
    assert card.view.shown.status is shown
    assert card.view.is_done


@pytest.mark.parametrize(
    "vocabulary",
    [
        pytest.param(user_vocabulary(unknown_lemmas={LEMMA}), id="unknown"),
        pytest.param(user_vocabulary(), id="nothing-anywhere"),
    ],
)
def test_a_word_open_here_stays_open(vocabulary: UserVocabulary) -> None:
    card = _open_card(vocabulary)

    assert card.elsewhere is None
    assert not any(b.pressed for b in card.view.buttons)
    assert not card.view.is_done


def test_a_word_decided_here_shows_its_own_decision() -> None:
    """Its own Learn is waiting for export too, but it is no other source's."""
    the_word = word(1, LEMMA, status=WordStatus.LEARN)
    cards = _cards(
        user_vocabulary(learning_lemmas={LEMMA}), the_word, occurrence(1, 1, is_decision=True),
    )

    [card] = cards.of_sources([10])

    assert card.elsewhere is None
    assert card.view.shown.status is WordStatus.LEARN


def test_cards_of_sources_follow_the_given_order() -> None:
    first, second = word(1, "glare", source_id=20), word(2, "stare", source_id=10)
    candidates = MagicMock()
    candidates.get_by_source.side_effect = lambda sid: {20: [first], 10: [second]}[sid]
    occurrences = MagicMock()
    occurrences.shown_by_word.side_effect = lambda sid: {
        20: {1: [occurrence(1, 1)]}, 10: {2: [occurrence(2, 2)]},
    }[sid]
    cards = ReviewCards(
        candidates, occurrences,
        PhraseWordStates(lambda: [first, second], lambda wid: [occurrence(wid, wid)]),
        user_vocabulary(),
    )
    assert [c.word.source_id for c in cards.of_sources([20, 10])] == [20, 10]

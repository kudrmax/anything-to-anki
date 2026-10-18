"""ReviewCards: whether a word open in a source is done via another one, read from the one
snapshot of what the user knows that the card view reads too."""
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_cards import ReviewCards
from backend.domain.value_objects.card_note import CardNote
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
    [found] = cards.of_source(10)
    assert cards.of_phrase(1) == found, "one card, however it is read"
    return found


@pytest.mark.parametrize(
    ("vocabulary", "elsewhere", "note", "shown"),
    [
        pytest.param(
            user_vocabulary(learning_lemmas={LEMMA}), ElsewhereStatus.LEARN,
            CardNote.LEARN_ELSEWHERE, WordStatus.LEARN, id="learn-waiting-for-export",
        ),
        pytest.param(
            user_vocabulary(active_since={LEMMA: FRESH}), ElsewhereStatus.LEARNING,
            CardNote.LEARNING_ELSEWHERE, WordStatus.LEARNING, id="in-anki",
        ),
        pytest.param(
            user_vocabulary(active_since={LEMMA: DUE}), ElsewhereStatus.KNOWN,
            CardNote.KNOWN_ELSEWHERE, WordStatus.KNOWN, id="known-by-timer",
        ),
        pytest.param(
            user_vocabulary(_known(LEMMA)), ElsewhereStatus.KNOWN,
            CardNote.KNOWN_ELSEWHERE, WordStatus.KNOWN, id="known-by-list",
        ),
    ],
)
def test_a_word_open_here_is_done_by_what_another_source_holds(
    vocabulary: UserVocabulary, elsewhere: ElsewhereStatus, note: CardNote, shown: WordStatus,
) -> None:
    card = _open_card(vocabulary)

    assert card.elsewhere is elsewhere
    assert card.view.note is note
    assert card.view.shown.status is shown
    assert card.view.is_done


@pytest.mark.parametrize(
    "vocabulary",
    [
        pytest.param(user_vocabulary(unknown_lemmas={LEMMA}, active_since={LEMMA: DUE}),
                     id="unknown-wins-over-the-timer"),
        pytest.param(user_vocabulary(unknown_lemmas={LEMMA}, learning_lemmas={LEMMA}),
                     id="unknown-wins-over-learn"),
        pytest.param(user_vocabulary(), id="nothing-anywhere"),
    ],
)
def test_a_word_open_here_stays_open(vocabulary: UserVocabulary) -> None:
    card = _open_card(vocabulary)

    assert card.elsewhere is None
    assert card.view.note is None
    assert not card.view.is_done


def test_a_word_decided_here_shows_its_own_decision() -> None:
    """Its own Learn is waiting for export too, but it is no other source's."""
    the_word = word(1, LEMMA, status=WordStatus.LEARN)
    cards = _cards(
        user_vocabulary(learning_lemmas={LEMMA}), the_word, occurrence(1, 1, is_decision=True),
    )

    [card] = cards.of_source(10)

    assert card.view.note is None
    assert card.view.shown.status is WordStatus.LEARN

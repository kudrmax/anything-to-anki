"""Unit tests for AddSavedPhraseUseCase.

A phrase met anywhere is saved with its picked target into the built-in
"Saved phrases" source, already marked to learn.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.source_dtos import card_to_dto
from backend.application.use_cases.add_saved_phrase import AddSavedPhraseUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import InvalidPhraseError, TargetNotInPhraseError
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase_origin_kind import DecisionKind, OccurrenceOrigin
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.word_status import WordStatus

from tests.card_support import card, occurrence, word
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.phrase import Phrase

pytestmark = pytest.mark.unit

SAVED_PHRASES_ID = 7
SAVED_PHRASE_ID = 41
WORD_ID = 100
PHRASE = "Stop   procrastinating, please."
_LEMMAS = {"procrastinating": "procrastinate"}


def _read_picked(text: str, picked: list[int]) -> Phrase:
    whole = phrase(text, lemmas=_LEMMAS)
    if not picked or any(not 0 <= i < len(whole.words) for i in picked):
        raise TargetNotInPhraseError()
    return whole.with_target(tuple(picked))


def _token(index: int, text: str, lemma: str) -> TokenData:
    return TokenData(
        index=index, text=text, lemma=lemma, pos="VERB", tag="VBG",
        head_index=0, children_indices=(), is_punct=False, is_stop=False,
        is_alpha=True, is_propn=False, sent_index=0,
    )


def _saved_phrases(source_id: int = SAVED_PHRASES_ID) -> Source:
    source = Source.saved_phrases()
    source.id = source_id
    return source


class _Setup:
    def __init__(self, existing: Source | None) -> None:
        self.source_repo = MagicMock()
        self.source_repo.get_first_by_role.return_value = existing
        self.source_repo.create.side_effect = lambda s: _saved_phrases(SAVED_PHRASES_ID + 1)
        self.candidate_repo = MagicMock()
        self.candidate_repo.add_word.return_value = WORD_ID
        self.occurrence_repo = MagicMock()
        self.occurrence_repo.word_rows.return_value = []
        self.occurrence_repo.add.side_effect = lambda occ: replace(occ, id=SAVED_PHRASE_ID)
        self.card_views = MagicMock()
        self.card_views.one.side_effect = lambda phrase_id: card_to_dto(card(
            word(WORD_ID, status=WordStatus.LEARN),
            occurrence(phrase_id, WORD_ID, is_decision=True, decision_kind=DecisionKind.LEARN),
        ))
        self.review_status = MagicMock()
        text_analyzer = MagicMock()
        text_analyzer.analyze.return_value = [_token(1, "procrastinating", "procrastinate")]
        cefr = MagicMock()
        cefr.classify_detailed.return_value = CEFRBreakdown(
            final_level=CEFRLevel.C1, decision_method="voting", priority_votes=[], votes=[],
        )
        frequency = MagicMock()
        frequency.get_zipf_value.return_value = 2.5
        detector = MagicMock()
        detector.detect.return_value = []
        reader = MagicMock()
        reader.read_picked.side_effect = _read_picked
        self.use_case = AddSavedPhraseUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            text_analyzer=text_analyzer,
            cefr_classifier=cefr,
            frequency_provider=frequency,
            phrasal_verb_detector=detector,
            review_status=self.review_status,
            phrase_reader=reader,
            occurrence_repo=self.occurrence_repo,
            card_views=self.card_views,
        )

    def saved_word(self) -> StoredCandidate:
        word: StoredCandidate = self.candidate_repo.add_word.call_args.args[0]
        return word

    def saved_phrase(self) -> Occurrence:
        added: Occurrence = self.occurrence_repo.add.call_args.args[0]
        return added


def test_phrase_is_saved_to_saved_phrases_source_marked_to_learn() -> None:
    setup = _Setup(existing=_saved_phrases())

    result = setup.use_case.execute(PHRASE, [1])

    saved_word, saved = setup.saved_word(), setup.saved_phrase()
    assert saved_word.source_id == SAVED_PHRASES_ID
    assert saved_word.lemma == "procrastinate"
    assert saved_word.occurrences == 1
    setup.candidate_repo.set_word_status.assert_called_once_with(WORD_ID, WordStatus.LEARN)
    assert saved.candidate_id == WORD_ID
    assert saved.origin is OccurrenceOrigin.COLLECTED
    assert (saved.is_decision, saved.decision_kind) == (True, DecisionKind.LEARN)
    assert saved.source_phrase.text == "Stop procrastinating, please."
    assert saved.source_phrase.target_text() == "procrastinating"
    assert saved.phrase_position is None
    assert result.status == "learn"
    setup.card_views.one.assert_called_once_with(SAVED_PHRASE_ID)
    setup.source_repo.get_first_by_role.assert_called_once_with(SourceRole.SAVED_PHRASES)
    setup.source_repo.create.assert_not_called()
    setup.review_status.refresh.assert_called_once_with(SAVED_PHRASES_ID)


def test_saved_phrases_source_is_created_when_missing() -> None:
    setup = _Setup(existing=None)

    setup.use_case.execute(PHRASE, [1])

    created: Source = setup.source_repo.create.call_args.args[0]
    assert created.role is SourceRole.SAVED_PHRASES
    assert setup.saved_word().source_id == SAVED_PHRASES_ID + 1


@pytest.mark.parametrize(("phrase", "target"), [
    ("   ", [0]),
    (PHRASE, []),
    (PHRASE, [5]),
])
def test_invalid_phrase_or_target_is_rejected(phrase: str, target: list[int]) -> None:
    setup = _Setup(existing=_saved_phrases())

    with pytest.raises(InvalidPhraseError):
        setup.use_case.execute(phrase, target)

    setup.candidate_repo.add_word.assert_not_called()
    setup.occurrence_repo.add.assert_not_called()

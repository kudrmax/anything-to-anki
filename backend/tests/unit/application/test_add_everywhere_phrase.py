"""Unit tests for AddEverywherePhraseUseCase.

A phrase met anywhere is saved with its picked target into the built-in
"From everywhere" source, already marked to learn.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.add_everywhere_phrase import AddEverywherePhraseUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import InvalidPhraseError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.content_type import ContentType

pytestmark = pytest.mark.unit

EVERYWHERE_ID = 7
PHRASE = "Stop   procrastinating, please."


def _token(index: int, text: str, lemma: str) -> TokenData:
    return TokenData(
        index=index, text=text, lemma=lemma, pos="VERB", tag="VBG",
        head_index=0, children_indices=(), is_punct=False, is_stop=False,
        is_alpha=True, is_propn=False, sent_index=0,
    )


def _everywhere(source_id: int = EVERYWHERE_ID) -> Source:
    source = Source.everywhere()
    source.id = source_id
    return source


def _saved(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
    return [
        StoredCandidate(**{**c.__dict__, "id": 100 + i}) for i, c in enumerate(candidates)
    ]


class _Setup:
    def __init__(self, existing: Source | None) -> None:
        self.source_repo = MagicMock()
        self.source_repo.get_first_by_content_type.return_value = existing
        self.source_repo.create.side_effect = lambda s: _everywhere(EVERYWHERE_ID + 1)
        self.candidate_repo = MagicMock()
        self.candidate_repo.create_batch.side_effect = _saved
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
        self.use_case = AddEverywherePhraseUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            text_analyzer=text_analyzer,
            cefr_classifier=cefr,
            frequency_provider=frequency,
            phrasal_verb_detector=detector,
            review_status=self.review_status,
        )

    def saved_candidate(self) -> StoredCandidate:
        candidate: StoredCandidate = self.candidate_repo.create_batch.call_args.args[0][0]
        return candidate


def test_phrase_is_saved_to_everywhere_source_marked_to_learn() -> None:
    setup = _Setup(existing=_everywhere())

    result = setup.use_case.execute(PHRASE, "procrastinating,")

    candidate = setup.saved_candidate()
    assert candidate.source_id == EVERYWHERE_ID
    assert candidate.status == CandidateStatus.LEARN
    assert candidate.lemma == "procrastinate"
    assert candidate.surface_form == "procrastinating"
    assert candidate.context_fragment == "Stop procrastinating, please."
    assert candidate.occurrences == 1
    assert result.status == "learn"
    setup.source_repo.get_first_by_content_type.assert_called_once_with(ContentType.PHRASES)
    setup.source_repo.create.assert_not_called()
    setup.review_status.refresh.assert_called_once_with(EVERYWHERE_ID)


def test_everywhere_source_is_created_when_missing() -> None:
    setup = _Setup(existing=None)

    setup.use_case.execute(PHRASE, "procrastinating")

    created: Source = setup.source_repo.create.call_args.args[0]
    assert created.content_type == ContentType.PHRASES
    assert setup.saved_candidate().source_id == EVERYWHERE_ID + 1


@pytest.mark.parametrize(("phrase", "target"), [
    ("   ", "word"),
    (PHRASE, ""),
    (PHRASE, "procrastinate"),
])
def test_invalid_phrase_or_target_is_rejected(phrase: str, target: str) -> None:
    setup = _Setup(existing=_everywhere())

    with pytest.raises(InvalidPhraseError):
        setup.use_case.execute(phrase, target)

    setup.candidate_repo.create_batch.assert_not_called()

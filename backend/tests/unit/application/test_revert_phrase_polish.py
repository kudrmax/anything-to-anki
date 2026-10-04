from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError, CandidateNotPolishedError
from backend.domain.value_objects.candidate_status import CandidateStatus


def _candidate(polished: str | None, reverted: bool = False) -> StoredCandidate:
    return StoredCandidate(
        id=5,
        source_id=1,
        lemma="stale",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="The air around us was stale",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
        polished_fragment=polished,
        polish_reverted=reverted,
    )


def _use_case(
    candidate: StoredCandidate | None,
) -> tuple[RevertPhrasePolishUseCase, MagicMock, MagicMock]:
    repo = MagicMock()
    repo.get_by_id.return_value = candidate
    reset = MagicMock()
    return RevertPhrasePolishUseCase(candidate_repo=repo, enrichment_reset=reset), repo, reset


@pytest.mark.unit
def test_revert_switches_phrase_and_drops_enrichments() -> None:
    use_case, repo, reset = _use_case(_candidate("The air was stale."))

    use_case.execute(5, reverted=True)

    repo.set_polish_reverted.assert_called_once_with(5, True)
    reset.reset.assert_called_once_with(5)


@pytest.mark.unit
def test_same_choice_changes_nothing() -> None:
    use_case, repo, reset = _use_case(_candidate("The air was stale.", reverted=True))

    use_case.execute(5, reverted=True)

    repo.set_polish_reverted.assert_not_called()
    reset.reset.assert_not_called()


@pytest.mark.unit
def test_unpolished_phrase_cannot_be_reverted() -> None:
    use_case, _, _ = _use_case(_candidate(None))

    with pytest.raises(CandidateNotPolishedError):
        use_case.execute(5, reverted=True)


@pytest.mark.unit
def test_missing_candidate() -> None:
    use_case, _, _ = _use_case(None)

    with pytest.raises(CandidateNotFoundError):
        use_case.execute(5, reverted=True)

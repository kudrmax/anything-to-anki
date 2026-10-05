from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError, InvalidPhraseError
from backend.domain.value_objects.candidate_status import CandidateStatus

SOURCE_PHRASE = "The air around us was stale"


def _candidate(polished: str | None = None, reverted: bool = False) -> StoredCandidate:
    return StoredCandidate(
        id=5,
        source_id=1,
        lemma="stale",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment=SOURCE_PHRASE,
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
        polished_fragment=polished,
        polish_reverted=reverted,
    )


def _use_case(candidate: StoredCandidate | None) -> tuple[EditCardPhraseUseCase, MagicMock]:
    candidate_repo = MagicMock()
    candidate_repo.get_by_id.return_value = candidate
    return EditCardPhraseUseCase(candidate_repo=candidate_repo), candidate_repo


@pytest.mark.unit
def test_edit_puts_phrase_on_card() -> None:
    use_case, repo = _use_case(_candidate())

    use_case.execute(5, "  The air was stale.  ")

    repo.set_polished_fragment.assert_called_once_with(5, "The air was stale.")
    repo.set_polish_reverted.assert_not_called()


@pytest.mark.unit
def test_edit_of_reverted_phrase_shows_the_edit() -> None:
    use_case, repo = _use_case(_candidate("The air was old.", reverted=True))

    use_case.execute(5, "The air was stale.")

    repo.set_polished_fragment.assert_called_once_with(5, "The air was stale.")
    repo.set_polish_reverted.assert_called_once_with(5, False)


@pytest.mark.unit
def test_unchanged_phrase_changes_nothing() -> None:
    use_case, repo = _use_case(_candidate("The air was stale."))

    use_case.execute(5, "The air was stale.")

    repo.set_polished_fragment.assert_not_called()


@pytest.mark.unit
def test_empty_phrase_is_rejected() -> None:
    use_case, repo = _use_case(_candidate())

    with pytest.raises(InvalidPhraseError):
        use_case.execute(5, "   ")
    repo.set_polished_fragment.assert_not_called()


@pytest.mark.unit
def test_missing_candidate() -> None:
    use_case, _ = _use_case(None)

    with pytest.raises(CandidateNotFoundError):
        use_case.execute(5, "The air was stale.")

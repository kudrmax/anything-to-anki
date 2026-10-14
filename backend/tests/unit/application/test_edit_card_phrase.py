from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
from backend.application.utils.rewrite_phrase import RewritePhrase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    CandidateNotFoundError,
    InvalidPhraseError,
    TargetNotInPhraseError,
)
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.candidate_status import CandidateStatus

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

SOURCE_PHRASE = "The air around us was stale"


def _read_for(text: str, lemma: str) -> Phrase:
    found = phrase(text, lemma)
    if not target_by_lemma(found.words, text, lemma):
        raise TargetNotInPhraseError()
    return found


def _candidate(polished: str | None = None, reverted: bool = False) -> StoredCandidate:
    return StoredCandidate(
        id=5,
        source_id=1,
        lemma="stale",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        source_phrase=phrase(SOURCE_PHRASE, "stale"),
        occurrences=1,
        status=CandidateStatus.PENDING,
        polished_phrase=phrase(polished, "stale") if polished is not None else None,
        polish_reverted=reverted,
    )


def _use_case(candidate: StoredCandidate | None) -> tuple[EditCardPhraseUseCase, MagicMock]:
    candidate_repo = MagicMock()
    candidate_repo.get_by_id.return_value = candidate
    reader = MagicMock()
    reader.read_for.side_effect = _read_for
    rewrite = RewritePhrase(
        candidate_repo=candidate_repo, phrase_reader=reader, occurrence_repo=MagicMock(),
    )
    use_case = EditCardPhraseUseCase(candidate_repo=candidate_repo, rewrite_phrase=rewrite)
    return use_case, candidate_repo


def _written(repo: MagicMock) -> list[tuple[int, str, str]]:
    return [
        (call.args[0], call.args[1].text, call.args[1].target_text())
        for call in repo.set_polished_phrase.call_args_list
    ]


@pytest.mark.unit
def test_edit_puts_phrase_on_card() -> None:
    use_case, repo = _use_case(_candidate())

    use_case.execute(5, "  The air was stale.  ")

    assert _written(repo) == [(5, "The air was stale.", "stale")]
    repo.set_polish_reverted.assert_not_called()


@pytest.mark.unit
def test_edit_of_reverted_phrase_shows_the_edit() -> None:
    """Storing the rewritten phrase clears the revert (the repository's contract)."""
    use_case, repo = _use_case(_candidate("The air was old and stale.", reverted=True))

    use_case.execute(5, "The air was stale.")

    assert _written(repo) == [(5, "The air was stale.", "stale")]


@pytest.mark.unit
def test_unchanged_phrase_changes_nothing() -> None:
    use_case, repo = _use_case(_candidate("The air was stale."))

    use_case.execute(5, "The air was stale.")

    repo.set_polished_phrase.assert_not_called()


@pytest.mark.unit
def test_empty_phrase_is_rejected() -> None:
    use_case, repo = _use_case(_candidate())

    with pytest.raises(InvalidPhraseError):
        use_case.execute(5, "   ")
    repo.set_polished_phrase.assert_not_called()


@pytest.mark.unit
def test_phrase_without_the_target_is_refused() -> None:
    use_case, repo = _use_case(_candidate())

    with pytest.raises(TargetNotInPhraseError):
        use_case.execute(5, "The air around us was fresh.")
    repo.set_polished_phrase.assert_not_called()


@pytest.mark.unit
def test_missing_candidate() -> None:
    use_case, _ = _use_case(None)

    with pytest.raises(CandidateNotFoundError):
        use_case.execute(5, "The air was stale.")

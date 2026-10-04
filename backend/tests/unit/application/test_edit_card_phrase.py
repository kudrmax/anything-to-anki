from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    CandidateNotFoundError,
    InvalidPhraseError,
    PhrasePolishNotSupportedError,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus

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


def _source(content_type: ContentType = ContentType.TEXT) -> Source:
    return Source(
        id=1,
        raw_text=SOURCE_PHRASE,
        status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED,
        content_type=content_type,
        created_at=datetime.now(tz=UTC),
    )


def _use_case(
    candidate: StoredCandidate | None, source: Source | None = None,
) -> tuple[EditCardPhraseUseCase, MagicMock, MagicMock]:
    candidate_repo = MagicMock()
    candidate_repo.get_by_id.return_value = candidate
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = source or _source()
    reset = MagicMock()
    use_case = EditCardPhraseUseCase(
        candidate_repo=candidate_repo, source_repo=source_repo, enrichment_reset=reset,
    )
    return use_case, candidate_repo, reset


@pytest.mark.unit
def test_edit_puts_phrase_on_card_and_drops_enrichments() -> None:
    use_case, repo, reset = _use_case(_candidate())

    use_case.execute(5, "  The air was stale.  ")

    repo.set_polished_fragment.assert_called_once_with(5, "The air was stale.")
    repo.set_polish_reverted.assert_not_called()
    reset.reset.assert_called_once_with(5)


@pytest.mark.unit
def test_edit_of_reverted_phrase_shows_the_edit() -> None:
    use_case, repo, _ = _use_case(_candidate("The air was old.", reverted=True))

    use_case.execute(5, "The air was stale.")

    repo.set_polished_fragment.assert_called_once_with(5, "The air was stale.")
    repo.set_polish_reverted.assert_called_once_with(5, False)


@pytest.mark.unit
def test_unchanged_phrase_changes_nothing() -> None:
    use_case, repo, reset = _use_case(_candidate("The air was stale."))

    use_case.execute(5, "The air was stale.")

    repo.set_polished_fragment.assert_not_called()
    reset.reset.assert_not_called()


@pytest.mark.unit
def test_empty_phrase_is_rejected() -> None:
    use_case, repo, _ = _use_case(_candidate())

    with pytest.raises(InvalidPhraseError):
        use_case.execute(5, "   ")
    repo.set_polished_fragment.assert_not_called()


@pytest.mark.unit
def test_video_phrase_stays_as_in_source() -> None:
    use_case, repo, _ = _use_case(_candidate(), _source(ContentType.VIDEO))

    with pytest.raises(PhrasePolishNotSupportedError):
        use_case.execute(5, "The air was stale.")
    repo.set_polished_fragment.assert_not_called()


@pytest.mark.unit
def test_missing_candidate() -> None:
    use_case, _, _ = _use_case(None)

    with pytest.raises(CandidateNotFoundError):
        use_case.execute(5, "The air was stale.")

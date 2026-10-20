from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
from backend.domain.exceptions import (
    CandidateNotPolishedError,
    PhraseNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

from tests.card_support import occurrence, word
from tests.lock_support import free_lock
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence

PHRASE_ID = 5
_STAMPER = MagicMock()
_STAMPER.earned.return_value = CandidateSection.EXTRA
SOURCE = phrase("The air around us was stale", "stale")


def _phrase(polished: str | None, reverted: bool = False) -> Occurrence:
    return occurrence(
        PHRASE_ID, 1, SOURCE,
        polished_phrase=phrase(polished, "stale") if polished is not None else None,
        polish_reverted=reverted,
    )


def _use_case(
    found: Occurrence | None, lock: MagicMock | None = None,
) -> tuple[RevertPhrasePolishUseCase, MagicMock, MagicMock]:
    occurrences = MagicMock()
    occurrences.get.return_value = found
    candidates = MagicMock()
    candidates.get_by_id.return_value = word(1, "stale")
    reset = MagicMock()
    use_case = RevertPhrasePolishUseCase(
        occurrence_repo=occurrences, candidate_repo=candidates, enrichment_reset=reset,
        lock=lock or free_lock(), stamper=_STAMPER,
    )
    return use_case, occurrences, reset


@pytest.mark.unit
def test_revert_switches_the_phrase_and_drops_its_enrichments() -> None:
    use_case, occurrences, reset = _use_case(_phrase("The air was stale."))

    use_case.execute(PHRASE_ID, reverted=True)

    occurrences.write_text.assert_called_once_with(
        PHRASE_ID, SOURCE, None, earned_section=CandidateSection.EXTRA,
        polished=phrase("The air was stale.", "stale"), polish_reverted=True,
    )
    _STAMPER.earned.assert_called_with(SOURCE, _STAMPER.earned.call_args.args[1])
    reset.reset_phrase.assert_called_once_with(PHRASE_ID)


@pytest.mark.unit
def test_same_choice_changes_nothing() -> None:
    use_case, occurrences, reset = _use_case(_phrase("The air was stale.", reverted=True))

    use_case.execute(PHRASE_ID, reverted=True)

    occurrences.write_text.assert_not_called()
    reset.reset_phrase.assert_not_called()


@pytest.mark.unit
def test_unpolished_phrase_cannot_be_reverted() -> None:
    use_case, _, _ = _use_case(_phrase(None))

    with pytest.raises(CandidateNotPolishedError):
        use_case.execute(PHRASE_ID, reverted=True)


@pytest.mark.unit
def test_missing_phrase() -> None:
    use_case, _, _ = _use_case(None)

    with pytest.raises(PhraseNotFoundError):
        use_case.execute(PHRASE_ID, reverted=True)


@pytest.mark.unit
def test_refused_while_the_source_is_busy() -> None:
    lock = MagicMock()
    lock.held.return_value = SourceOperationKind.UPDATE
    use_case, occurrences, _ = _use_case(_phrase("The air was stale."), lock)

    with pytest.raises(SourceOperationBusyError):
        use_case.execute(PHRASE_ID, reverted=True)
    occurrences.write_text.assert_not_called()

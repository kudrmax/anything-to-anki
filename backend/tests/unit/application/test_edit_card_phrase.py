from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
from backend.application.utils.rewrite_phrase import RewritePhrase
from backend.domain.exceptions import (
    InvalidPhraseError,
    PhraseNotFoundError,
    SourceOperationBusyError,
    TargetNotInPhraseError,
)
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

from tests.card_support import occurrence, word
from tests.lock_support import free_lock
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.phrase import Phrase

PHRASE_ID = 5
SOURCE_PHRASE = "The air around us was stale"


def _read_for(text: str, lemma: str) -> Phrase:
    found = phrase(text, lemma)
    if not target_by_lemma(found.words, text, lemma):
        raise TargetNotInPhraseError()
    return found


def _phrase(polished: str | None = None, reverted: bool = False) -> Occurrence:
    return occurrence(
        PHRASE_ID, 1, phrase(SOURCE_PHRASE, "stale"),
        polished_phrase=phrase(polished, "stale") if polished is not None else None,
        polish_reverted=reverted,
    )


def _use_case(
    found: Occurrence | None, lock: MagicMock | None = None,
) -> tuple[EditCardPhraseUseCase, MagicMock]:
    occurrences = MagicMock()
    occurrences.get.return_value = found
    candidates = MagicMock()
    candidates.get_by_id.return_value = word(1, "stale")
    reader = MagicMock()
    reader.read_for.side_effect = _read_for
    stamper = MagicMock()
    stamper.earned.return_value = CandidateSection.EXTRA
    rewrite = RewritePhrase(phrase_reader=reader, occurrence_repo=occurrences, stamper=stamper)
    use_case = EditCardPhraseUseCase(
        occurrence_repo=occurrences, candidate_repo=candidates, rewrite_phrase=rewrite,
        lock=lock or free_lock(),
    )
    return use_case, occurrences


def _written(occurrences: MagicMock) -> list[tuple[int, str, str, bool]]:
    return [
        (
            call.args[0], call.kwargs["polished"].text, call.kwargs["polished"].target_text(),
            call.kwargs.get("polish_reverted", False),
        )
        for call in occurrences.write_text.call_args_list
    ]


@pytest.mark.unit
def test_edit_puts_the_text_on_the_card_phrase() -> None:
    use_case, occurrences = _use_case(_phrase())

    use_case.execute(PHRASE_ID, "  The air was stale.  ")

    assert _written(occurrences) == [(PHRASE_ID, "The air was stale.", "stale", False)]
    stored = occurrences.write_text.call_args.kwargs["earned_section"]
    assert stored is CandidateSection.EXTRA, "the edited text is stamped"


@pytest.mark.unit
def test_edit_of_reverted_phrase_shows_the_edit() -> None:
    use_case, occurrences = _use_case(_phrase("The air was old and stale.", reverted=True))

    use_case.execute(PHRASE_ID, "The air was stale.")

    assert _written(occurrences) == [(PHRASE_ID, "The air was stale.", "stale", False)]


@pytest.mark.unit
def test_unchanged_phrase_changes_nothing() -> None:
    use_case, occurrences = _use_case(_phrase("The air was stale."))

    use_case.execute(PHRASE_ID, "The air was stale.")

    occurrences.write_text.assert_not_called()


@pytest.mark.unit
def test_empty_phrase_is_rejected() -> None:
    use_case, occurrences = _use_case(_phrase())

    with pytest.raises(InvalidPhraseError):
        use_case.execute(PHRASE_ID, "   ")
    occurrences.write_text.assert_not_called()


@pytest.mark.unit
def test_phrase_without_the_target_is_refused() -> None:
    use_case, occurrences = _use_case(_phrase())

    with pytest.raises(TargetNotInPhraseError):
        use_case.execute(PHRASE_ID, "The air around us was fresh.")
    occurrences.write_text.assert_not_called()


@pytest.mark.unit
def test_missing_phrase() -> None:
    use_case, _ = _use_case(None)

    with pytest.raises(PhraseNotFoundError):
        use_case.execute(PHRASE_ID, "The air was stale.")


@pytest.mark.unit
def test_refused_while_the_source_is_busy() -> None:
    lock = MagicMock()
    lock.held.return_value = SourceOperationKind.REBUILD
    use_case, occurrences = _use_case(_phrase(), lock)

    with pytest.raises(SourceOperationBusyError):
        use_case.execute(PHRASE_ID, "The air was stale.")
    occurrences.write_text.assert_not_called()

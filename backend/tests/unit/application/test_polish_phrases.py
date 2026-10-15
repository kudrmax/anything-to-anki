from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
from backend.application.utils.generation_targets import GenerationCard
from backend.application.utils.rewrite_phrase import RewritePhrase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import make_occurrence, phrase
from tests.word_support import phrase_id_of

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

_CONFIG = PromptsConfig(
    generate_meaning_user_template="",
    generate_meaning_system="",
    generate_topic_targets_user_template="",
    generate_topic_targets_system="",
    polish_phrase_user_template=(
        'Target form: "{surface_form}"\nPhrase: "{phrase}"\nAround: "{context}"'
    ),
    polish_phrase_system="Make it easy for {cefr_level}.",
)
_SOURCE_PHRASE = "What had once been a barn had been abandoned partway through"
_TEXT = f"It rained. {_SOURCE_PHRASE}. Lillian was halfway down."
_DOCUMENT = Document((Paragraph(lines=(Line(_TEXT),), mode=ParagraphMode.FLOW),))
_PHRASE_START = _TEXT.index(_SOURCE_PHRASE)
_PHRASE = DocumentPosition(0, 0, _PHRASE_START, 0, _PHRASE_START + len(_SOURCE_PHRASE))
_LEMMAS = {"abandoned": "abandon"}


def _read_for(text: str, lemma: str) -> Phrase:
    found = phrase(text, lemma, lemmas=_LEMMAS)
    if not target_by_lemma(found.words, text, lemma):
        raise TargetNotInPhraseError()
    return found


def _polished(repo: MagicMock) -> list[tuple[int, str]]:
    """Phrase id → the polished text written, in order."""
    return [
        (call.args[0], call.kwargs["polished"].text) for call in repo.write_text.call_args_list
    ]


def _candidate(
    cid: int = 1,
    *,
    status: WordStatus = WordStatus.PENDING,
    polished: str | None = None,
) -> GenerationCard:
    """Word `cid` and its phrase `phrase_id_of(cid)`."""
    word = StoredCandidate(
        id=cid,
        source_id=9,
        lemma="abandon",
        pos="VERB",
        cefr_level="B1",
        zipf_frequency=4.0,
        occurrences=1,
        status=status,
    )
    shown = replace(
        make_occurrence(_SOURCE_PHRASE, candidate_id=cid),
        id=phrase_id_of(cid),
        source_phrase=phrase(_SOURCE_PHRASE, "abandoned"),
        polished_phrase=phrase(polished, "abandoned") if polished is not None else None,
        phrase_position=_PHRASE,
    )
    return GenerationCard.of(word, shown, None)


P1, P2 = phrase_id_of(1), phrase_id_of(2)


def _refs(*phrase_ids: int) -> list[PhraseRef]:
    return [PhraseRef(phrase_id, 0) for phrase_id in phrase_ids]


def _source(source_format: Format = Format.PLAIN) -> Source:
    return Source(
        id=9,
        status=SourceStatus.DONE, format=source_format, kind=Kind.TEXT,
        )


def _use_case(
    candidates: list[GenerationCard],
    answers: list[PolishedPhrase],
    source: Source | None = None,
    *,
    holds: bool = True,
) -> tuple[PhrasePolishUseCase, MagicMock, MagicMock, MagicMock]:
    job_phrases = MagicMock()
    job_phrases.cards.return_value = candidates
    job_phrases.holds.return_value = holds
    occurrence_repo = MagicMock()
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = source or _source()
    settings_repo = MagicMock()
    settings_repo.get.return_value = "B1"
    ai_service = MagicMock()
    ai_service.polish_phrases_batch.return_value = answers
    reset = MagicMock()
    document_repo = MagicMock()
    document_repo.get.return_value = _DOCUMENT
    reader = MagicMock()
    reader.read_for.side_effect = _read_for
    use_case = PhrasePolishUseCase(
        job_phrases=job_phrases,
        occurrence_repo=occurrence_repo,
        source_repo=source_repo,
        document_repo=document_repo,
        settings_repo=settings_repo,
        enrichment_reset=reset,
        ai_service=ai_service,
        prompts_config=_CONFIG,
        rewrite_phrase=RewritePhrase(reader, occurrence_repo),
    )
    return use_case, occurrence_repo, ai_service, reset


@pytest.mark.unit
def test_stores_polished_phrase_and_drops_old_enrichments() -> None:
    easy = "People abandoned the old barn."
    use_case, repo, _, reset = _use_case([_candidate()], [PolishedPhrase(1, easy)])

    use_case.execute_batch(_refs(P1))

    assert _polished(repo) == [(P1, easy)]
    reset.reset_phrase.assert_called_once_with(P1)


@pytest.mark.unit
def test_prompt_carries_user_level_target_form_and_surrounding_text() -> None:
    use_case, _, ai, _ = _use_case([_candidate()], [])

    use_case.execute_batch(_refs(P1))

    system, user = ai.polish_phrases_batch.call_args.args
    assert system == "Make it easy for B1."
    assert user.startswith("Phrase 1:\n")
    assert 'Target form: "abandoned"' in user
    assert f'Around: "{_TEXT}"' in user


@pytest.mark.unit
def test_unchanged_answer_is_stored_without_dropping_enrichments() -> None:
    use_case, repo, _, reset = _use_case(
        [_candidate()], [PolishedPhrase(1, _SOURCE_PHRASE)],
    )

    use_case.execute_batch(_refs(P1))

    assert _polished(repo) == [(P1, _SOURCE_PHRASE)]
    reset.reset_phrase.assert_not_called()


@pytest.mark.unit
def test_answer_without_target_keeps_source_phrase() -> None:
    use_case, repo, _, reset = _use_case(
        [_candidate()], [PolishedPhrase(1, "People left the old barn.")],
    )

    use_case.execute_batch(_refs(P1))

    assert _polished(repo) == [(P1, _SOURCE_PHRASE)]
    reset.reset_phrase.assert_not_called()


@pytest.mark.unit
def test_answer_is_cleaned_of_bold_and_quotes() -> None:
    use_case, repo, _, _ = _use_case(
        [_candidate()], [PolishedPhrase(1, '"People **abandoned**  the barn."')],
    )

    use_case.execute_batch(_refs(P1))

    assert _polished(repo) == [(P1, "People abandoned the barn.")]


@pytest.mark.unit
def test_skips_decided_and_already_polished_cards() -> None:
    use_case, repo, ai, _ = _use_case(
        [_candidate(1, status=WordStatus.KNOWN), _candidate(2, polished="x abandoned")],
        [],
    )

    use_case.execute_batch(_refs(P1, P2))

    ai.polish_phrases_batch.assert_not_called()
    repo.write_text.assert_not_called()


@pytest.mark.unit
def test_video_cards_are_not_polished() -> None:
    use_case, _, ai, _ = _use_case([_candidate()], [], source=_source(Format.VIDEO_FILE))

    use_case.execute_batch(_refs(P1))

    ai.polish_phrases_batch.assert_not_called()


@pytest.mark.unit
def test_cards_ai_did_not_answer_are_reported() -> None:
    easy = "People abandoned the old barn."
    use_case, repo, _, _ = _use_case(
        [_candidate(1), _candidate(2)], [PolishedPhrase(1, easy)],
    )

    assert use_case.execute_batch(_refs(P1, P2)) == [P2]
    assert _polished(repo) == [(P1, easy)]


@pytest.mark.unit
def test_cards_no_longer_wanted_are_left_untouched() -> None:
    easy = "People abandoned the old barn."
    use_case, repo, _, reset = _use_case(
        [_candidate(1), _candidate(2)], [PolishedPhrase(1, easy), PolishedPhrase(2, easy)],
    )

    assert use_case.execute_batch(_refs(P1, P2), still_wanted=lambda ids: {P1}) == []
    assert _polished(repo) == [(P1, easy)]
    reset.reset_phrase.assert_called_once_with(P1)


@pytest.mark.unit
def test_a_phrase_changed_while_ai_answered_keeps_its_text() -> None:
    use_case, repo, _, reset = _use_case(
        [_candidate()], [PolishedPhrase(1, "People abandoned the old barn.")], holds=False,
    )

    assert use_case.execute_batch(_refs(P1)) == []
    repo.write_text.assert_not_called()
    reset.reset_phrase.assert_not_called()

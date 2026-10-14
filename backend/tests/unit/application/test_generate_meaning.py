from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.application.utils.requested_cards import RequestedCards
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    PhraseChangedError,
    PhraseNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.generation_result import GenerationResult
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import make_occurrence

_CONFIG = PromptsConfig(
    generate_meaning_user_template='Word: "{lemma}" ({pos})\nContext: "{context}"',
    generate_meaning_system="SYSTEM PROMPT",
    generate_topic_targets_user_template="Request: {query}",
    generate_topic_targets_system="TOPIC SYSTEM PROMPT",
    polish_phrase_user_template="Phrase: {phrase}",
    polish_phrase_system="POLISH SYSTEM PROMPT for {cefr_level}",
)


PHRASE_ID = 7


def _use_case(
    meaning_repo: MagicMock,
    ai_service: MagicMock,
    *,
    phrase_found: bool = True,
    busy_with: SourceOperationKind | None = None,
    holds: bool = True,
) -> GenerateMeaningUseCase:
    """Word 1 with phrase 7 "Could you elaborate on that?"."""
    shown = replace(
        make_occurrence("Could you elaborate on that?", candidate_id=1), id=PHRASE_ID,
    )
    occurrence_repo = MagicMock()
    occurrence_repo.get.return_value = shown if phrase_found else None
    occurrence_repo.holds_revision.return_value = holds
    candidate_repo = MagicMock()
    candidate_repo.get_by_id.return_value = _make_candidate()
    lock = MagicMock()
    lock.held.return_value = busy_with
    return GenerateMeaningUseCase(
        cards=RequestedCards(candidate_repo, occurrence_repo, lock),
        occurrence_repo=occurrence_repo,
        meaning_repo=meaning_repo,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )


def _make_candidate(cid: int = 1) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=1,
        lemma="elaborate",
        pos="VERB",
        status=WordStatus.PENDING,
        cefr_level=None,
        zipf_frequency=4.5,
        occurrences=1,
        is_phrasal_verb=False,
    )


@pytest.mark.unit
def test_generate_meaning_happy_path() -> None:
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    ai_service.generate_meaning.return_value = GenerationResult(
        meaning="explain in detail",
        translation="разъяснить",
        synonyms="explain, clarify",
        examples="Could you **elaborate** on that point?",
        ipa="/ɪˈlæb.ə.reɪt/",
        tokens_used=42,
    )

    result = _use_case(meaning_repo, ai_service).execute(PHRASE_ID)

    assert result.meaning == "explain in detail"
    assert result.translation == "разъяснить"
    assert result.synonyms == "explain, clarify"
    assert result.ipa == "/ɪˈlæb.ə.reɪt/"
    assert result.tokens_used == 42

    ai_service.generate_meaning.assert_called_once()
    args, _ = ai_service.generate_meaning.call_args
    assert args[0] == "SYSTEM PROMPT"
    assert "elaborate" in args[1]
    assert "(VERB)" in args[1]
    assert "Could you elaborate on that?" in args[1]

    meaning_repo.upsert_for_phrase.assert_called_once()
    phrase_id, upserted = meaning_repo.upsert_for_phrase.call_args[0]
    assert (phrase_id, upserted.candidate_id) == (PHRASE_ID, 1)
    assert upserted.meaning == "explain in detail"
    assert upserted.translation == "разъяснить"
    assert upserted.synonyms == "explain, clarify"
    assert isinstance(upserted.generated_at, datetime)


@pytest.mark.unit
def test_generate_meaning_phrase_not_found() -> None:
    with pytest.raises(PhraseNotFoundError):
        _use_case(MagicMock(), MagicMock(), phrase_found=False).execute(PHRASE_ID)


@pytest.mark.unit
def test_generate_meaning_is_refused_while_the_source_is_rebuilt() -> None:
    ai_service = MagicMock()

    with pytest.raises(SourceOperationBusyError):
        _use_case(
            MagicMock(), ai_service, busy_with=SourceOperationKind.REBUILD,
        ).execute(PHRASE_ID)
    ai_service.generate_meaning.assert_not_called()


@pytest.mark.unit
def test_a_meaning_for_a_phrase_changed_meanwhile_is_not_stored() -> None:
    meaning_repo = MagicMock()
    ai_service = MagicMock()
    ai_service.generate_meaning.return_value = GenerationResult(
        meaning="m", translation="t", synonyms="s", examples="e", ipa=None, tokens_used=1,
    )

    with pytest.raises(PhraseChangedError):
        _use_case(meaning_repo, ai_service, holds=False).execute(PHRASE_ID)
    meaning_repo.upsert_for_phrase.assert_not_called()


def _existing_meaning(cid: int = 1) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=cid,
        meaning="explain in detail",
        translation="разъяснить",
        synonyms="explain, clarify",
        examples="Some example",
        ipa="/ɪˈlæb.ə.reɪt/",
        generated_at=None,
    )


@pytest.mark.unit
def test_follow_up_explain_detail_replaces_meaning() -> None:
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    meaning_repo.get_by_phrase_id.return_value = _existing_meaning()
    ai_service.generate_follow_up.return_value = GenerationResult(
        meaning="detailed explanation",
        translation="разъяснить",
        synonyms="explain, clarify",
        examples="",
        ipa="/ɪˈlæb.ə.reɪt/",
        tokens_used=30,
    )

    use_case = _use_case(meaning_repo, ai_service)
    result = use_case.execute_follow_up(PHRASE_ID, "explain_detail", None)

    ai_service.generate_follow_up.assert_called_once()
    ai_service.generate_meaning.assert_not_called()
    assert result.meaning == "detailed explanation"
    phrase_id, upserted = meaning_repo.upsert_for_phrase.call_args[0]
    assert (phrase_id, upserted.meaning) == (PHRASE_ID, "detailed explanation")


@pytest.mark.unit
def test_follow_up_give_examples_appends_to_examples() -> None:
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    meaning_repo.get_by_phrase_id.return_value = _existing_meaning()
    ai_service.generate_follow_up.return_value = GenerationResult(
        meaning="New example sentence",
        translation="",
        synonyms="",
        examples="",
        ipa=None,
        tokens_used=20,
    )

    use_case = _use_case(meaning_repo, ai_service)
    result = use_case.execute_follow_up(PHRASE_ID, "give_examples", None)

    # Original meaning preserved
    assert result.meaning == "explain in detail"
    # Examples appended
    assert "Some example" in result.examples
    assert "New example sentence" in result.examples


@pytest.mark.unit
def test_follow_up_how_to_say_appends_to_meaning() -> None:
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    meaning_repo.get_by_phrase_id.return_value = _existing_meaning()
    ai_service.generate_follow_up.return_value = GenerationResult(
        meaning="You can say: Let me elaborate.",
        translation="",
        synonyms="",
        examples="",
        ipa=None,
        tokens_used=15,
    )

    use_case = _use_case(meaning_repo, ai_service)
    result = use_case.execute_follow_up(PHRASE_ID, "how_to_say", None)

    assert "explain in detail" in result.meaning
    assert "Let me elaborate" in result.meaning


@pytest.mark.unit
def test_follow_up_free_question_without_text_raises() -> None:
    use_case = _use_case(MagicMock(), MagicMock())

    with pytest.raises(ValueError, match="requires text"):
        use_case.execute_follow_up(PHRASE_ID, "free_question", None)

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.generation_result import GenerationResult
from backend.domain.value_objects.prompts_config import PromptsConfig

_CONFIG = PromptsConfig(
    generate_meaning_user_template='Word: "{lemma}" ({pos})\nContext: "{context}"',
    generate_meaning_system="SYSTEM PROMPT",
)


def _make_candidate(cid: int = 1) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=1,
        lemma="elaborate",
        surface_form="elaborate",
        pos="VERB",
        context_fragment="Could you elaborate on that?",
        status=CandidateStatus.PENDING,
        cefr_level=None,
        zipf_frequency=4.5,
        fragment_purity="clean",
        occurrences=1,
        is_phrasal_verb=False,
        meaning=None,
        media=None,
    )


@pytest.mark.unit
def test_generate_meaning_happy_path() -> None:
    candidate_repo = MagicMock()
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    ai_service.generate_meaning.return_value = GenerationResult(
        meaning="explain in detail",
        translation="разъяснить",
        synonyms="explain, clarify",
        examples="Could you **elaborate** on that point?",
        ipa="/ɪˈlæb.ə.reɪt/",
        tokens_used=42,
    )

    use_case = GenerateMeaningUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=meaning_repo,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )
    result = use_case.execute(candidate_id=1)

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

    meaning_repo.upsert.assert_called_once()
    upserted = meaning_repo.upsert.call_args[0][0]
    assert upserted.candidate_id == 1
    assert upserted.meaning == "explain in detail"
    assert upserted.translation == "разъяснить"
    assert upserted.synonyms == "explain, clarify"
    assert upserted.status == EnrichmentStatus.DONE
    assert isinstance(upserted.generated_at, datetime)


@pytest.mark.unit
def test_generate_meaning_candidate_not_found() -> None:
    candidate_repo = MagicMock()
    candidate_repo.get_by_id.return_value = None

    use_case = GenerateMeaningUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=MagicMock(),
        ai_service=MagicMock(),
        prompts_config=_CONFIG,
    )

    with pytest.raises(CandidateNotFoundError):
        use_case.execute(candidate_id=99)


def _existing_meaning(cid: int = 1) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=cid,
        meaning="explain in detail",
        translation="разъяснить",
        synonyms="explain, clarify",
        examples="Some example",
        ipa="/ɪˈlæb.ə.reɪt/",
        status=EnrichmentStatus.DONE,
        error=None,
        generated_at=None,
    )


def _make_follow_up_use_case(
    candidate_repo: MagicMock,
    meaning_repo: MagicMock,
    ai_service: MagicMock,
) -> GenerateMeaningUseCase:
    return GenerateMeaningUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=meaning_repo,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )


@pytest.mark.unit
def test_follow_up_explain_detail_replaces_meaning() -> None:
    candidate_repo = MagicMock()
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    meaning_repo.get_by_candidate_id.return_value = _existing_meaning()
    ai_service.generate_meaning.return_value = GenerationResult(
        meaning="detailed explanation",
        translation="разъяснить",
        synonyms="explain, clarify",
        examples="",
        ipa="/ɪˈlæb.ə.reɪt/",
        tokens_used=30,
    )

    use_case = _make_follow_up_use_case(candidate_repo, meaning_repo, ai_service)
    result = use_case.execute_follow_up(1, "explain_detail", None)

    assert result.meaning == "detailed explanation"
    upserted = meaning_repo.upsert.call_args[0][0]
    assert upserted.meaning == "detailed explanation"


@pytest.mark.unit
def test_follow_up_give_examples_appends_to_examples() -> None:
    candidate_repo = MagicMock()
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    meaning_repo.get_by_candidate_id.return_value = _existing_meaning()
    ai_service.generate_meaning.return_value = GenerationResult(
        meaning="New example sentence",
        translation="",
        synonyms="",
        examples="",
        ipa=None,
        tokens_used=20,
    )

    use_case = _make_follow_up_use_case(candidate_repo, meaning_repo, ai_service)
    result = use_case.execute_follow_up(1, "give_examples", None)

    # Original meaning preserved
    assert result.meaning == "explain in detail"
    # Examples appended
    assert "Some example" in result.examples
    assert "New example sentence" in result.examples


@pytest.mark.unit
def test_follow_up_how_to_say_appends_to_meaning() -> None:
    candidate_repo = MagicMock()
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    meaning_repo.get_by_candidate_id.return_value = _existing_meaning()
    ai_service.generate_meaning.return_value = GenerationResult(
        meaning="You can say: Let me elaborate.",
        translation="",
        synonyms="",
        examples="",
        ipa=None,
        tokens_used=15,
    )

    use_case = _make_follow_up_use_case(candidate_repo, meaning_repo, ai_service)
    result = use_case.execute_follow_up(1, "how_to_say", None)

    assert "explain in detail" in result.meaning
    assert "Let me elaborate" in result.meaning


@pytest.mark.unit
def test_follow_up_free_question_without_text_raises() -> None:
    candidate_repo = MagicMock()
    meaning_repo = MagicMock()
    ai_service = MagicMock()

    use_case = _make_follow_up_use_case(candidate_repo, meaning_repo, ai_service)

    with pytest.raises(ValueError, match="requires text"):
        use_case.execute_follow_up(1, "free_question", None)

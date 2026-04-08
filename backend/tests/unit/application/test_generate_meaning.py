from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
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
        is_sweet_spot=True,
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

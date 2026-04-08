from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.prompts_config import PromptsConfig


_CONFIG = PromptsConfig(
    generate_meaning_user_template='Word: "{lemma}" ({pos})\nContext: "{context}"',
    generate_meaning_system="SYSTEM PROMPT",
)


def _make_candidate(cid: int, lemma: str, *, with_meaning: bool = False) -> StoredCandidate:
    meaning = None
    if with_meaning:
        meaning = CandidateMeaning(
            candidate_id=cid,
            meaning="already done",
            translation=None,
            synonyms=None,
            ipa=None,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=None,
        )
    return StoredCandidate(
        id=cid,
        source_id=1,
        lemma=lemma,
        surface_form=lemma,
        pos="VERB",
        context_fragment=f"Could you {lemma} on that?",
        status=CandidateStatus.PENDING,
        cefr_level=None,
        zipf_frequency=4.5,
        is_sweet_spot=True,
        fragment_purity="clean",
        occurrences=1,
        is_phrasal_verb=False,
        meaning=meaning,
        media=None,
    )


def _running_meaning(cid: int) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=cid,
        meaning=None,
        translation=None,
        synonyms=None,
        ipa=None,
        status=EnrichmentStatus.RUNNING,
        error=None,
        generated_at=None,
    )


@pytest.mark.unit
def test_execute_batch_empty_list_is_noop() -> None:
    candidate_repo = MagicMock()
    ai_service = MagicMock()

    use_case = MeaningGenerationUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=MagicMock(),
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )
    use_case.execute_batch([])

    candidate_repo.get_by_ids.assert_not_called()
    ai_service.generate_meanings_batch.assert_not_called()


@pytest.mark.unit
def test_execute_batch_happy_path() -> None:
    c1 = _make_candidate(1, "elaborate")
    c2 = _make_candidate(2, "reluctant")

    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = [c1, c2]

    meaning_repo = MagicMock()
    meaning_repo.get_by_candidate_id.side_effect = lambda cid: _running_meaning(cid)

    ai_service = MagicMock()
    ai_service.generate_meanings_batch.return_value = [
        BatchMeaningResult(word_index=1, meaning="explain more", translation="объяснить", synonyms="explain, elaborate", ipa=None),
        BatchMeaningResult(word_index=2, meaning="unwilling", translation="неохотный", synonyms="hesitant, unwilling", ipa=None),
    ]

    use_case = MeaningGenerationUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=meaning_repo,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )
    use_case.execute_batch([1, 2])

    ai_service.generate_meanings_batch.assert_called_once()
    args, _ = ai_service.generate_meanings_batch.call_args
    assert args[0] == "SYSTEM PROMPT"
    assert "elaborate" in args[1]
    assert "reluctant" in args[1]
    assert "Word 1:" in args[1]
    assert "Word 2:" in args[1]

    assert meaning_repo.upsert.call_count == 2
    upserts = [call.args[0] for call in meaning_repo.upsert.call_args_list]
    by_id = {m.candidate_id: m for m in upserts}
    assert by_id[1].meaning == "explain more"
    assert by_id[2].meaning == "unwilling"
    assert by_id[1].translation == "объяснить"
    assert by_id[1].synonyms == "explain, elaborate"
    assert by_id[2].translation == "неохотный"
    assert by_id[2].synonyms == "hesitant, unwilling"
    assert by_id[1].status == EnrichmentStatus.DONE
    assert by_id[2].status == EnrichmentStatus.DONE


@pytest.mark.unit
def test_execute_batch_skips_candidates_with_meaning() -> None:
    c1 = _make_candidate(1, "elaborate", with_meaning=True)
    c2 = _make_candidate(2, "reluctant")

    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = [c1, c2]

    meaning_repo = MagicMock()
    meaning_repo.get_by_candidate_id.side_effect = lambda cid: _running_meaning(cid)

    ai_service = MagicMock()
    ai_service.generate_meanings_batch.return_value = [
        BatchMeaningResult(word_index=1, meaning="unwilling", translation="неохотный", synonyms="hesitant, unwilling", ipa=None),
    ]

    use_case = MeaningGenerationUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=meaning_repo,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )
    use_case.execute_batch([1, 2])

    args, _ = ai_service.generate_meanings_batch.call_args
    assert args[1].count("Word ") == 1
    assert "reluctant" in args[1]
    assert "elaborate" not in args[1]

    assert meaning_repo.upsert.call_count == 1
    upserted = meaning_repo.upsert.call_args[0][0]
    assert upserted.candidate_id == 2


@pytest.mark.unit
def test_execute_batch_skips_cancelled_candidate() -> None:
    c1 = _make_candidate(1, "elaborate")

    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = [c1]

    cancelled = CandidateMeaning(
        candidate_id=1,
        meaning=None,
        translation=None,
        synonyms=None,
        ipa=None,
        status=EnrichmentStatus.FAILED,
        error="cancelled by user",
        generated_at=None,
    )
    meaning_repo = MagicMock()
    meaning_repo.get_by_candidate_id.return_value = cancelled

    ai_service = MagicMock()
    ai_service.generate_meanings_batch.return_value = [
        BatchMeaningResult(word_index=1, meaning="explain more", translation="объяснить", synonyms="explain, elaborate", ipa=None),
    ]

    use_case = MeaningGenerationUseCase(
        candidate_repo=candidate_repo,
        meaning_repo=meaning_repo,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )
    use_case.execute_batch([1])

    meaning_repo.upsert.assert_not_called()

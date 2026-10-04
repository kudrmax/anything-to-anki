from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.domain.value_objects.source_status import SourceStatus

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


def _candidate(
    cid: int = 1,
    *,
    status: CandidateStatus = CandidateStatus.PENDING,
    polished: str | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=9,
        lemma="abandon",
        surface_form="abandoned",
        pos="VERB",
        cefr_level="B1",
        zipf_frequency=4.0,
        context_fragment=_SOURCE_PHRASE,
        fragment_purity="clean",
        occurrences=1,
        status=status,
        polished_fragment=polished,
    )


def _source(content_type: ContentType = ContentType.TEXT) -> Source:
    return Source(
        id=9,
        raw_text=_TEXT,
        status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED,
        content_type=content_type,
    )


def _use_case(
    candidates: list[StoredCandidate],
    answers: list[PolishedPhrase],
    source: Source | None = None,
) -> tuple[PhrasePolishUseCase, MagicMock, MagicMock, MagicMock]:
    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = candidates
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = source or _source()
    settings_repo = MagicMock()
    settings_repo.get.return_value = "B1"
    ai_service = MagicMock()
    ai_service.polish_phrases_batch.return_value = answers
    reset = MagicMock()
    use_case = PhrasePolishUseCase(
        candidate_repo=candidate_repo,
        source_repo=source_repo,
        settings_repo=settings_repo,
        enrichment_reset=reset,
        ai_service=ai_service,
        prompts_config=_CONFIG,
    )
    return use_case, candidate_repo, ai_service, reset


@pytest.mark.unit
def test_stores_polished_phrase_and_drops_old_enrichments() -> None:
    easy = "People abandoned the old barn."
    use_case, repo, _, reset = _use_case([_candidate()], [PolishedPhrase(1, easy)])

    use_case.execute_batch([1])

    repo.set_polished_fragment.assert_called_once_with(1, easy)
    reset.reset.assert_called_once_with(1)


@pytest.mark.unit
def test_prompt_carries_user_level_target_form_and_surrounding_text() -> None:
    use_case, _, ai, _ = _use_case([_candidate()], [])

    use_case.execute_batch([1])

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

    use_case.execute_batch([1])

    repo.set_polished_fragment.assert_called_once_with(1, _SOURCE_PHRASE)
    reset.reset.assert_not_called()


@pytest.mark.unit
def test_answer_without_target_keeps_source_phrase() -> None:
    use_case, repo, _, reset = _use_case(
        [_candidate()], [PolishedPhrase(1, "People left the old barn.")],
    )

    use_case.execute_batch([1])

    repo.set_polished_fragment.assert_called_once_with(1, _SOURCE_PHRASE)
    reset.reset.assert_not_called()


@pytest.mark.unit
def test_answer_is_cleaned_of_bold_and_quotes() -> None:
    use_case, repo, _, _ = _use_case(
        [_candidate()], [PolishedPhrase(1, '"People **abandoned**  the barn."')],
    )

    use_case.execute_batch([1])

    repo.set_polished_fragment.assert_called_once_with(1, "People abandoned the barn.")


@pytest.mark.unit
def test_skips_decided_and_already_polished_cards() -> None:
    use_case, repo, ai, _ = _use_case(
        [_candidate(1, status=CandidateStatus.KNOWN), _candidate(2, polished="x abandoned")],
        [],
    )

    use_case.execute_batch([1, 2])

    ai.polish_phrases_batch.assert_not_called()
    repo.set_polished_fragment.assert_not_called()


@pytest.mark.unit
def test_video_cards_are_not_polished() -> None:
    use_case, _, ai, _ = _use_case([_candidate()], [], source=_source(ContentType.VIDEO))

    use_case.execute_batch([1])

    ai.polish_phrases_batch.assert_not_called()

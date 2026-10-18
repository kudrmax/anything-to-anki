from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.application.utils.generation_targets import GenerationCard
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.domain.value_objects.word_status import WordStatus

from tests.card_support import context
from tests.phrase_support import make_occurrence

_CONFIG = PromptsConfig(
    generate_meaning_user_template='Word: "{lemma}" ({pos})\nContext: "{context}"',
    generate_meaning_system="SYSTEM PROMPT",
    generate_topic_targets_user_template="Request: {query}",
    generate_topic_targets_system="TOPIC SYSTEM PROMPT",
    polish_phrase_user_template="Phrase: {phrase}",
    polish_phrase_system="POLISH SYSTEM PROMPT for {cefr_level}",
)


def _card(
    cid: int,
    lemma: str,
    *,
    with_meaning: bool = False,
    status: WordStatus = WordStatus.NEW,
    skipped: bool = False,
) -> GenerationCard:
    """Word `cid` and its phrase cid * 10."""
    word = StoredCandidate(
        id=cid,
        source_id=1,
        lemma=lemma,
        pos="VERB",
        status=status,
        cefr_level=None,
        zipf_frequency=4.5,
        occurrences=1,
    )
    shown = make_occurrence(
        f"Could you {lemma} on that?", candidate_id=cid,
        meaning_text="already done" if with_meaning else None,
    )
    phrase = replace(
        shown, id=cid * 10, choice=CardChoice.SKIP if skipped else CardChoice.NONE,
    )
    return GenerationCard.of(word, phrase, context(word, phrase))


def _refs(*phrase_ids: int) -> list[PhraseRef]:
    return [PhraseRef(phrase_id, 0) for phrase_id in phrase_ids]


def _answer(*indexes: int) -> list[BatchMeaningResult]:
    return [
        BatchMeaningResult(
            word_index=i, meaning=f"meaning {i}", translation=f"translation {i}",
            synonyms=f"synonyms {i}", examples="", ipa=None,
        )
        for i in indexes
    ]


class _Setup:
    def __init__(self, cards: list[GenerationCard], *, stale: set[int] | None = None) -> None:
        self.job_phrases = MagicMock()
        self.job_phrases.cards.return_value = cards
        self.job_phrases.holds.side_effect = lambda card: card.phrase_id not in (stale or set())
        self.meaning_repo = MagicMock()
        self.ai_service = MagicMock()
        self.use_case = MeaningGenerationUseCase(
            job_phrases=self.job_phrases,
            meaning_repo=self.meaning_repo,
            ai_service=self.ai_service,
            prompts_config=_CONFIG,
        )

    def written(self) -> dict[int, tuple[int, str | None]]:
        """Phrase id → (word id, meaning) of every meaning stored."""
        return {
            call.args[0]: (call.args[1].candidate_id, call.args[1].meaning)
            for call in self.meaning_repo.upsert_for_phrase.call_args_list
        }


@pytest.mark.unit
def test_execute_batch_empty_list_is_noop() -> None:
    setup = _Setup([])

    setup.use_case.execute_batch([])

    setup.job_phrases.cards.assert_not_called()
    setup.ai_service.generate_meanings_batch.assert_not_called()


@pytest.mark.unit
def test_execute_batch_happy_path() -> None:
    setup = _Setup([_card(1, "elaborate"), _card(2, "reluctant")])
    setup.ai_service.generate_meanings_batch.return_value = _answer(1, 2)

    setup.use_case.execute_batch(_refs(10, 20))

    args, _ = setup.ai_service.generate_meanings_batch.call_args
    assert args[0] == "SYSTEM PROMPT"
    assert "Word 1:" in args[1] and "Word 2:" in args[1]
    assert "Could you elaborate on that?" in args[1]
    assert "reluctant" in args[1]
    assert setup.written() == {10: (1, "meaning 1"), 20: (2, "meaning 2")}
    stored = setup.meaning_repo.upsert_for_phrase.call_args_list[0].args[1]
    assert (stored.translation, stored.synonyms) == ("translation 1", "synonyms 1")


@pytest.mark.unit
def test_execute_batch_skips_phrases_with_meaning() -> None:
    setup = _Setup([_card(1, "elaborate", with_meaning=True), _card(2, "reluctant")])
    setup.ai_service.generate_meanings_batch.return_value = _answer(1)

    setup.use_case.execute_batch(_refs(10, 20))

    args, _ = setup.ai_service.generate_meanings_batch.call_args
    assert args[1].count("Word ") == 1
    assert "reluctant" in args[1]
    assert "elaborate" not in args[1]
    assert setup.written() == {20: (2, "meaning 1")}


@pytest.mark.unit
def test_execute_batch_returns_early_when_all_phrases_filtered() -> None:
    """Done, known and skipped cards need no meaning: AI is not asked at all."""
    known = _card(2, "known", status=WordStatus.KNOWN)
    skipped = _card(3, "skipped", skipped=True)
    setup = _Setup([_card(1, "done", with_meaning=True), known, skipped])

    setup.use_case.execute_batch(_refs(10, 20, 30))

    setup.ai_service.generate_meanings_batch.assert_not_called()
    setup.meaning_repo.upsert_for_phrase.assert_not_called()


@pytest.mark.unit
def test_execute_batch_reports_phrase_without_ai_result() -> None:
    """When the AI returns fewer results than requested, the missing phrase is
    reported back instead of silently staying without a meaning."""
    setup = _Setup([_card(1, "first"), _card(2, "second")])
    setup.ai_service.generate_meanings_batch.return_value = _answer(1)

    unanswered = setup.use_case.execute_batch(_refs(10, 20))

    assert unanswered == [20]
    assert setup.written() == {10: (1, "meaning 1")}


@pytest.mark.unit
def test_execute_batch_writes_only_phrases_still_wanted() -> None:
    setup = _Setup([_card(1, "a"), _card(2, "b")])
    setup.ai_service.generate_meanings_batch.return_value = _answer(1, 2)

    unanswered = setup.use_case.execute_batch(_refs(10, 20), still_wanted=lambda ids: {20})

    assert unanswered == []
    assert list(setup.written()) == [20]


@pytest.mark.unit
def test_a_phrase_changed_while_ai_answered_gets_nothing_and_is_not_reported() -> None:
    setup = _Setup([_card(1, "a"), _card(2, "b")], stale={10})
    setup.ai_service.generate_meanings_batch.return_value = _answer(2)

    unanswered = setup.use_case.execute_batch(_refs(10, 20))

    assert unanswered == []
    assert setup.written() == {20: (2, "meaning 2")}

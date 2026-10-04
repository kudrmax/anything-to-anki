from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.generate_topic_targets import (
    TOPIC_TARGET_COUNT,
    GenerateTopicTargetsUseCase,
)
from backend.domain.entities.source import Source
from backend.domain.exceptions import PermanentAIError, SourceNotFoundError
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.topic_target_draft import TopicTargetDraft

pytestmark = pytest.mark.unit

SOURCE_ID = 3
_CONFIG = PromptsConfig(
    generate_meaning_user_template="Word: {lemma}",
    generate_meaning_system="MEANING SYSTEM",
    generate_topic_targets_user_template="Request: {query} | {cefr_level} | {count}",
    generate_topic_targets_system="TOPIC SYSTEM",
    polish_phrase_user_template="Phrase: {phrase}",
    polish_phrase_system="POLISH SYSTEM PROMPT for {cefr_level}",
)


class TestGenerateTopicTargets:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.source_repo.get_by_id.return_value = Source(
            id=SOURCE_ID,
            raw_text="  negotiating a salary ",
            status=SourceStatus.NEW,
            input_method=InputMethod.TOPIC_QUERY,
            content_type=ContentType.TOPIC,
        )
        self.topic_target_repo = MagicMock()
        self.topic_target_repo.has_targets.return_value = False
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = "B2"
        self.ai_service = MagicMock()
        self.use_case = GenerateTopicTargetsUseCase(
            source_repo=self.source_repo,
            topic_target_repo=self.topic_target_repo,
            settings_repo=self.settings_repo,
            ai_service=self.ai_service,
            prompts_config=_CONFIG,
        )

    def _saved(self) -> list[tuple[int, str, str]]:
        (targets,), _ = self.topic_target_repo.create_batch.call_args
        return [(t.position, t.phrase, t.example) for t in targets]

    def test_builds_prompt_from_request_and_level(self) -> None:
        self.ai_service.generate_topic_targets.return_value = [
            TopicTargetDraft(phrase="negotiate", example="We **negotiate** the offer."),
        ]
        self.use_case.execute(SOURCE_ID)

        self.ai_service.generate_topic_targets.assert_called_once_with(
            "TOPIC SYSTEM",
            f"Request: negotiating a salary | B2 | {TOPIC_TARGET_COUNT}",
        )

    def test_keeps_usable_unique_targets_in_order(self) -> None:
        self.ai_service.generate_topic_targets.return_value = [
            TopicTargetDraft(phrase=" negotiate ", example="We **negotiate** the offer."),
            TopicTargetDraft(phrase="raise", example="No marked target here."),
            TopicTargetDraft(phrase="Negotiate", example="They **negotiated** hard."),
            TopicTargetDraft(phrase="meet halfway", example="Let's **meet halfway**."),
        ]
        self.use_case.execute(SOURCE_ID)

        assert self._saved() == [
            (0, "negotiate", "We **negotiate** the offer."),
            (1, "meet halfway", "Let's **meet halfway**."),
        ]

    def test_nothing_usable_is_a_permanent_error(self) -> None:
        self.ai_service.generate_topic_targets.return_value = [
            TopicTargetDraft(phrase="raise", example="No marked target here."),
        ]
        with pytest.raises(PermanentAIError):
            self.use_case.execute(SOURCE_ID)
        self.topic_target_repo.create_batch.assert_not_called()

    def test_existing_targets_are_not_regenerated(self) -> None:
        self.topic_target_repo.has_targets.return_value = True
        self.use_case.execute(SOURCE_ID)
        self.ai_service.generate_topic_targets.assert_not_called()

    def test_missing_source_raises(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(SOURCE_ID)

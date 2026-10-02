from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.entities.topic_target import TopicTarget
from backend.domain.exceptions import PermanentAIError, SourceNotFoundError
from backend.domain.services.topic_phrase_selection import parse_marked_phrase

if TYPE_CHECKING:
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.topic_target_repository import TopicTargetRepository
    from backend.domain.value_objects.prompts_config import PromptsConfig
    from backend.domain.value_objects.topic_target_draft import TopicTargetDraft

logger = logging.getLogger(__name__)

TOPIC_TARGET_COUNT = 20
MAX_PHRASE_LENGTH = 100
DEFAULT_CEFR_LEVEL = "B1"


class GenerateTopicTargetsUseCase:
    """Asks AI which targets to study for a topic request and stores them.

    Runs in the worker. Idempotent: a topic that already has targets is left
    untouched, so a retried job never calls AI twice.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        topic_target_repo: TopicTargetRepository,
        settings_repo: SettingsRepository,
        ai_service: AIService,
        prompts_config: PromptsConfig,
    ) -> None:
        self._source_repo = source_repo
        self._topic_target_repo = topic_target_repo
        self._settings_repo = settings_repo
        self._ai_service = ai_service
        self._prompts_config = prompts_config

    def execute(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        if self._topic_target_repo.has_targets(source_id):
            logger.info("generate_topic_targets: already generated (source_id=%d)", source_id)
            return

        cefr_level = (
            self._settings_repo.get("cefr_level", DEFAULT_CEFR_LEVEL) or DEFAULT_CEFR_LEVEL
        )
        user_prompt = self._prompts_config.generate_topic_targets_user_template.format(
            query=source.raw_text.strip(),
            cefr_level=cefr_level,
            count=TOPIC_TARGET_COUNT,
        )
        drafts = self._ai_service.generate_topic_targets(
            self._prompts_config.generate_topic_targets_system, user_prompt,
        )
        usable = _deduplicate([d for d in drafts if _is_usable(d)])
        if not usable:
            raise PermanentAIError("AI returned no usable targets for this topic")

        self._topic_target_repo.create_batch([
            TopicTarget(
                source_id=source_id,
                position=position,
                phrase=draft.phrase.strip(),
                example=draft.example.strip(),
            )
            for position, draft in enumerate(usable)
        ])
        logger.info(
            "generate_topic_targets: done (source_id=%d, proposed=%d, kept=%d)",
            source_id, len(drafts), len(usable),
        )


def _is_usable(draft: TopicTargetDraft) -> bool:
    phrase = draft.phrase.strip()
    return 0 < len(phrase) <= MAX_PHRASE_LENGTH and parse_marked_phrase(draft.example) is not None


def _deduplicate(drafts: list[TopicTargetDraft]) -> list[TopicTargetDraft]:
    seen: set[str] = set()
    unique: list[TopicTargetDraft] = []
    for draft in drafts:
        key = draft.phrase.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(draft)
    return unique

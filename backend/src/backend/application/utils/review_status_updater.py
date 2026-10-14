from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import derive_review_status

if TYPE_CHECKING:
    from backend.application.utils.review_progress import ReviewProgress
    from backend.domain.entities.source import Source
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.decision_progress import DecisionProgress


class ReviewStatusUpdater:
    """Пересчитывает статус ревью источника после изменения его кандидатов.

    Источник разобран, когда разобраны все его карточки Ready: остальные не держат его.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        review_progress: ReviewProgress,
        occurrence_repo: OccurrenceRepository,
    ) -> None:
        self._source_repo = source_repo
        self._review_progress = review_progress
        self._occurrence_repo = occurrence_repo

    def refresh(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is not None:
            self._refresh(source)

    def refresh_all(self) -> None:
        """После того как изменилось, какие слова пользователь знает: карточки сменили разделы.
        Прогресс всех источников читается одной лёгкой проекцией."""
        sources = self._source_repo.list_all()
        progress = self._review_progress.of_sources([s.id for s in sources if s.id is not None])
        for source in sources:
            assert source.id is not None
            self._apply(source, progress[source.id])

    def refresh_showing(self, lemmas: set[str]) -> None:
        """После того как изменилось, знает ли или учит ли пользователь эти слова: только
        источники, где они есть среди слов показанных фраз."""
        for source_id in sorted(self._occurrence_repo.sources_showing(lemmas)):
            self.refresh(source_id)

    def _refresh(self, source: Source) -> None:
        assert source.id is not None
        self._apply(source, self._review_progress.of_source(source.id))

    def _apply(self, source: Source, progress: DecisionProgress) -> None:
        assert source.id is not None
        status = derive_review_status(source.status, progress)
        if status != source.status:
            self._source_repo.update_status(source.id, status)

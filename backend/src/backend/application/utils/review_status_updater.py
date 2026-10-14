from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.source_review_status import derive_review_status

if TYPE_CHECKING:
    from backend.application.utils.candidate_sorter import CandidateSorter
    from backend.domain.entities.source import Source
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.source_repository import SourceRepository


class ReviewStatusUpdater:
    """Пересчитывает статус ревью источника после изменения его кандидатов.

    Источник разобран, когда разобраны все его карточки Ready: остальные не держат его.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        candidate_repo: CandidateRepository,
        candidate_sorter: CandidateSorter,
    ) -> None:
        self._source_repo = source_repo
        self._candidate_repo = candidate_repo
        self._candidate_sorter = candidate_sorter

    def refresh(self, source_id: int) -> None:
        source = self._source_repo.get_by_id(source_id)
        if source is not None:
            self._refresh(source)

    def refresh_all(self) -> None:
        """После того как изменилось, какие слова пользователь знает: карточки сменили разделы."""
        for source in self._source_repo.list_all():
            self._refresh(source)

    def _refresh(self, source: Source) -> None:
        assert source.id is not None
        candidates = self._candidate_repo.get_by_source(source.id)
        ready = self._candidate_sorter.arrange(candidates).ready()
        status = derive_review_status(source.status, (c.status for c in ready))
        if status != source.status:
            self._source_repo.update_status(source.id, status)

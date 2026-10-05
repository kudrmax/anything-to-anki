from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.services.export_readiness import export_group
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.value_objects.export_group import ExportGroup


@dataclass(frozen=True)
class ExportBatch:
    """'Learn' candidates still waiting for export, plus how many already went to Anki."""

    pending: list[StoredCandidate]
    exported_count: int

    def in_group(self, group: ExportGroup) -> list[StoredCandidate]:
        return [c for c in self.pending if export_group(c) == group]


class ExportQueue:
    """Splits 'learn' candidates into not yet exported and already sent to Anki."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        anki_sync_repo: AnkiSyncRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._anki_sync_repo = anki_sync_repo

    def for_source(self, source_id: int) -> ExportBatch:
        candidates = self._candidate_repo.get_by_source(source_id)
        return self._split([c for c in candidates if c.status == CandidateStatus.LEARN])

    def for_all(self) -> ExportBatch:
        return self._split(self._candidate_repo.get_all_by_status(CandidateStatus.LEARN))

    def _split(self, learn: list[StoredCandidate]) -> ExportBatch:
        candidate_ids = [c.id for c in learn if c.id is not None]
        exported = self._anki_sync_repo.get_synced_candidate_ids(candidate_ids)
        pending = [c for c in learn if c.id not in exported]
        return ExportBatch(pending=pending, exported_count=len(learn) - len(pending))

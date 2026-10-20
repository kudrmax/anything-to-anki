from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.fix_sections_dtos import FixSectionsReportDTO
from backend.domain.services.rebuild_plan import SectionChange
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_operation_kind import SourceOperationKind

if TYPE_CHECKING:
    from backend.application.use_cases.rebuild_source import RebuildSourceUseCase
    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class FixSectionsUseCase:
    """Brings the data from before the stored sections up to date: gives every phrase without
    a section the one it earns now, then updates each source that can be updated (no phrase
    text changes; cards of words no longer new go) so the sections of its phrases follow
    what the user knows."""

    def __init__(
        self,
        source_repo: SourceRepository,
        occurrence_repo: OccurrenceRepository,
        stamper: SectionStamper,
        rebuild_source: RebuildSourceUseCase,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._source_repo = source_repo
        self._occurrence_repo = occurrence_repo
        self._stamper = stamper
        self._rebuild_source = rebuild_source
        self._unit_of_work = unit_of_work

    def execute(self) -> FixSectionsReportDTO:
        stamped = self._stamp_unsectioned()
        rebuilt, failed = self._rebuild_sources()
        return FixSectionsReportDTO(
            phrases_stamped=stamped, sources_rebuilt=rebuilt, failed=failed,
        )

    def _stamp_unsectioned(self) -> int:
        with self._unit_of_work.write():
            phrases = self._occurrence_repo.unsectioned()
            rule = self._stamper.rule()
            self._occurrence_repo.set_earned_sections([
                SectionChange(occurrence_id=p.id, earned_section=rule.earned(p.phrase, p))
                for p in phrases
            ])
        logger.info("fix sections: %d phrases stamped", len(phrases))
        return len(phrases)

    def _rebuild_sources(self) -> tuple[int, list[int]]:
        rebuilt = 0
        failed: list[int] = []
        for source in self._source_repo.list_all():
            if source.id is None:
                continue
            if SourceOperationKind.UPDATE not in available_operations(source):
                continue
            try:
                self._rebuild_source.execute(source.id, RebuildMode.UPDATE)
            except Exception:
                logger.exception("fix sections: rebuild of source %d failed", source.id)
                self._unit_of_work.rollback()
                failed.append(source.id)
            else:
                rebuilt += 1
                logger.info("fix sections: source %d rebuilt", source.id)
        return rebuilt, failed

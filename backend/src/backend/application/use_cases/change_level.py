from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import CEFR_LEVEL_SETTING, FREQUENT_WORD_THRESHOLD_SETTING
from backend.application.utils.long_operation_runner import Applied, SourceWork
from backend.application.utils.source_rebuilder import AnalysisValues
from backend.domain.services.source_operations import REBUILD_OPERATION, available_operations
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.application.dto.settings_dtos import UpdateSettingsRequest
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.long_operation_runner import LongOperationRunner
    from backend.application.utils.settings_writer import SettingsWriter
    from backend.application.utils.source_rebuilder import AnalysedSource, SourceRebuilder
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.services.long_operation_progress import PartReport

MODE = RebuildMode.UPDATE


class ChangeLevelUseCase:
    """Saves settings that change the analysis together with «Find words again» of every
    source and the card states, in one write: all of it or none.

    Runs as a long operation once its lock is held: every source is analysed with the new
    values first, then the settings and every source are applied in one write. A source
    that cannot be analysed fails the whole change."""

    def __init__(
        self,
        settings_writer: SettingsWriter,
        threshold_resolver: FrequentWordThresholdResolver,
        scope_resolver: SourceScopeResolver,
        rebuilder: SourceRebuilder,
        runner: LongOperationRunner,
    ) -> None:
        self._settings_writer = settings_writer
        self._threshold_resolver = threshold_resolver
        self._scope_resolver = scope_resolver
        self._rebuilder = rebuilder
        self._runner = runner

    def execute(self, request: UpdateSettingsRequest) -> None:
        self._runner.run(_LevelChange(
            request, self._settings_writer, self._rebuilder,
            values=lambda: self._values(request), targets=self._targets,
        ))

    def _values(self, request: UpdateSettingsRequest) -> AnalysisValues:
        threshold = self._settings_writer.after(request, FREQUENT_WORD_THRESHOLD_SETTING)
        level = self._settings_writer.after(request, CEFR_LEVEL_SETTING)
        return AnalysisValues(
            user_level=level,
            frequent_word_zipf=self._threshold_resolver.resolve_for(
                threshold, CEFRLevel.from_str(level),
            ).zipf,
        )

    def _targets(self) -> list[int]:
        """Sources that failed processing are left out: their analysis fails every time,
        and would keep the level from ever changing. Their Update applies the new level."""
        offered = REBUILD_OPERATION[MODE]
        return [
            source.id for source in self._scope_resolver.sources(SourceScope.all())
            if source.id is not None and source.status is not SourceStatus.ERROR
            and offered in available_operations(source)
        ]


class _LevelChange(SourceWork["AnalysedSource", None]):
    """Every source analysed with the new values; the settings saved in the same write."""

    def __init__(
        self,
        request: UpdateSettingsRequest,
        settings_writer: SettingsWriter,
        rebuilder: SourceRebuilder,
        values: Callable[[], AnalysisValues],
        targets: Callable[[], list[int]],
    ) -> None:
        self._request = request
        self._settings_writer = settings_writer
        self._rebuilder = rebuilder
        self._read_values = values
        self._read_targets = targets
        self._values: AnalysisValues | None = None

    def targets(self) -> list[int]:
        self._values = self._read_values()
        return self._read_targets()

    def sizes(self, source_ids: Sequence[int]) -> dict[int, int]:
        return self._rebuilder.sizes(source_ids)

    def prepare(self, source_id: int, report: PartReport) -> AnalysedSource:
        return self._rebuilder.analyse(source_id, self._values, report)

    def apply_first(self) -> None:
        self._settings_writer.write(self._request)

    def apply(self, prepared: AnalysedSource) -> Applied[None]:
        return Applied(None, self._rebuilder.apply_inside(prepared, MODE).dropped_files)

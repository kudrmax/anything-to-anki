from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.delete_sources import DeleteSourcesUseCase
from backend.domain.exceptions import PermanentSourceError, SourceIsProcessingError


@pytest.mark.unit
def test_deletes_what_it_can_and_reports_the_rest() -> None:
    delete_source = MagicMock()
    delete_source.execute.side_effect = [None, SourceIsProcessingError(2), PermanentSourceError(3)]
    result = DeleteSourcesUseCase(delete_source).execute([1, 2, 3])
    assert (result.deleted, result.skipped) == ([1], [2, 3])

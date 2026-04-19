from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus


@pytest.mark.unit
class TestGetCandidatesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.use_case = GetCandidatesUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            settings_repo=self.settings_repo,
        )

    def test_returns_candidates_for_source(self) -> None:
        self.source_repo.get_by_id.return_value = MagicMock()
        self.candidate_repo.get_by_source.return_value = [
            StoredCandidate(
                id=1, source_id=1, lemma="test", pos="NOUN",
                cefr_level="B2", zipf_frequency=3.5,
                context_fragment="a test", fragment_purity="clean",
                occurrences=1, status=CandidateStatus.PENDING,
            ),
        ]
        result = self.use_case.execute(1)
        assert len(result) == 1
        assert result[0].lemma == "test"

    def test_source_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(999)

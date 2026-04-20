from unittest.mock import MagicMock

import pytest
from backend.application.dto.source_dtos import stored_candidate_to_dto
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


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

    def test_to_dto_maps_pronunciation(self) -> None:
        pronunciation = CandidatePronunciation(
            candidate_id=1,
            us_audio_path="/audio/us/test.mp3",
            uk_audio_path="/audio/uk/test.mp3",
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=None,
        )
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="test", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="a test", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
            pronunciation=pronunciation,
        )
        dto = stored_candidate_to_dto(candidate)
        assert dto.pronunciation is not None
        assert dto.pronunciation.us_audio_path == "/audio/us/test.mp3"
        assert dto.pronunciation.uk_audio_path == "/audio/uk/test.mp3"
        assert dto.pronunciation.status == EnrichmentStatus.DONE.value

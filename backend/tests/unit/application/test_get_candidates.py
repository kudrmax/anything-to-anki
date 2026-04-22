from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from backend.application.dto.source_dtos import stored_candidate_to_dto
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.job import Job
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.usage_distribution import UsageDistribution


@pytest.mark.unit
class TestGetCandidatesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.job_repo = MagicMock()
        self.job_repo.get_jobs_for_candidates.return_value = {}
        self.use_case = GetCandidatesUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            settings_repo=self.settings_repo,
            job_repo=self.job_repo,
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
        assert dto.pronunciation.status == "done"

    def test_to_dto_maps_frequency_band_mid(self) -> None:
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="test", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.8,
            context_fragment="a test", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        )
        dto = stored_candidate_to_dto(candidate)
        assert dto.frequency_band == "MID"

    def test_to_dto_maps_frequency_band_rare(self) -> None:
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="esoteric", pos="ADJ",
            cefr_level="C2", zipf_frequency=1.5,
            context_fragment="an esoteric topic", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        )
        dto = stored_candidate_to_dto(candidate)
        assert dto.frequency_band == "RARE"

    def test_to_dto_maps_usage_distribution(self) -> None:
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="gonna", pos="VERB",
            cefr_level="B1", zipf_frequency=4.0,
            context_fragment="gonna do it", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
            usage_distribution=UsageDistribution(groups={"informal": 0.8, "neutral": 0.2}),
        )
        dto = stored_candidate_to_dto(candidate)
        assert dto.usage_distribution == {"informal": 0.8, "neutral": 0.2}

    def test_to_dto_maps_usage_distribution_none(self) -> None:
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="test", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="a test", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
            usage_distribution=None,
        )
        dto = stored_candidate_to_dto(candidate)
        assert dto.usage_distribution is None

    def test_dto_has_queued_status_when_job_exists(self) -> None:
        """Candidate with a QUEUED meaning job gets status='queued' in DTO."""
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="test", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="a test", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
        )
        self.source_repo.get_by_id.return_value = MagicMock()
        self.candidate_repo.get_by_source.return_value = [candidate]

        queued_job = Job(
            id=100, job_type=JobType.MEANING, candidate_id=1,
            source_id=1, status=JobStatus.QUEUED, error=None,
            created_at=now, started_at=None,
        )
        self.job_repo.get_jobs_for_candidates.return_value = {
            1: {"meaning": queued_job},
        }

        result = self.use_case.execute(1)
        assert len(result) == 1
        assert result[0].meaning is not None
        assert result[0].meaning.status == "queued"

    def test_dto_has_done_status_when_no_job(self) -> None:
        """Candidate with meaning data and no job gets status='done'."""
        now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation="тест",
            synonyms=None, examples=None, ipa=None, generated_at=now,
        )
        candidate = StoredCandidate(
            id=1, source_id=1, lemma="test", pos="NOUN",
            cefr_level="B2", zipf_frequency=3.5,
            context_fragment="a test", fragment_purity="clean",
            occurrences=1, status=CandidateStatus.PENDING,
            meaning=meaning,
        )
        self.source_repo.get_by_id.return_value = MagicMock()
        self.candidate_repo.get_by_source.return_value = [candidate]
        self.job_repo.get_jobs_for_candidates.return_value = {}

        result = self.use_case.execute(1)
        assert len(result) == 1
        assert result[0].meaning is not None
        assert result[0].meaning.status == "done"

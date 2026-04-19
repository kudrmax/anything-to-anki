from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestGetSourcesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.use_case = GetSourcesUseCase(
            source_repo=self.source_repo,
            candidate_repo=self.candidate_repo,
            settings_repo=self.settings_repo,
        )

    def test_list_all(self) -> None:
        self.source_repo.list_all.return_value = [
            Source(id=1, raw_text="Text one", status=SourceStatus.NEW,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT),
            Source(id=2, raw_text="Text two", status=SourceStatus.DONE,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT),
        ]
        self.candidate_repo.get_by_source.return_value = []
        result = self.use_case.list_all()
        assert len(result) == 2
        assert result[0].id == 1

    def test_list_all_learn_count(self) -> None:
        from backend.domain.entities.stored_candidate import StoredCandidate

        self.source_repo.list_all.return_value = [
            Source(id=1, raw_text="Text one", status=SourceStatus.DONE,
                   input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT),
        ]
        make_candidate = lambda status: StoredCandidate(  # noqa: E731
            id=1, source_id=1, lemma="word", pos="NOUN", cefr_level="B2",
            zipf_frequency=4.0, context_fragment="ctx",
            fragment_purity="clean", occurrences=1, status=status,
        )
        self.candidate_repo.get_by_source.return_value = [
            make_candidate(CandidateStatus.LEARN),
            make_candidate(CandidateStatus.LEARN),
            make_candidate(CandidateStatus.PENDING),
            make_candidate(CandidateStatus.KNOWN),
        ]
        result = self.use_case.list_all()
        assert result[0].candidate_count == 4
        assert result[0].learn_count == 2

    def test_get_by_id_found(self) -> None:
        self.source_repo.get_by_id.return_value = Source(
            id=1, raw_text="Hello", status=SourceStatus.DONE,
            input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
        )
        self.candidate_repo.get_by_source.return_value = []
        result = self.use_case.get_by_id(1)
        assert result.id == 1

    def test_get_by_id_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.get_by_id(999)

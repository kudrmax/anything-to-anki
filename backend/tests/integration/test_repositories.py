import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import (
    SqlaSettingsRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)
from sqlalchemy.orm import Session


@pytest.mark.integration
class TestSourceRepository:
    def test_create_and_get(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = Source(raw_text="Hello world", status=SourceStatus.NEW)
        created = repo.create(source)
        assert created.id is not None
        assert created.raw_text == "Hello world"
        assert created.status == SourceStatus.NEW

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.raw_text == "Hello world"

    def test_list_all(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        repo.create(Source(raw_text="Text 1", status=SourceStatus.NEW))
        repo.create(Source(raw_text="Text 2", status=SourceStatus.NEW))
        sources = repo.list_all()
        assert len(sources) == 2

    def test_update_status(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = repo.create(Source(raw_text="Test", status=SourceStatus.NEW))
        assert source.id is not None
        repo.update_status(source.id, SourceStatus.DONE, cleaned_text="Cleaned test")
        updated = repo.get_by_id(source.id)
        assert updated is not None
        assert updated.status == SourceStatus.DONE
        assert updated.cleaned_text == "Cleaned test"

    def test_update_status_error(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = repo.create(Source(raw_text="Test", status=SourceStatus.NEW))
        assert source.id is not None
        repo.update_status(source.id, SourceStatus.ERROR, error_message="Something broke")
        updated = repo.get_by_id(source.id)
        assert updated is not None
        assert updated.status == SourceStatus.ERROR
        assert updated.error_message == "Something broke"

    def test_get_nonexistent(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        assert repo.get_by_id(999) is None


@pytest.mark.integration
class TestCandidateRepository:
    def _create_source(self, db_session: Session) -> int:
        repo = SqlaSourceRepository(db_session)
        source = repo.create(Source(raw_text="Test", status=SourceStatus.DONE))
        assert source.id is not None
        return source.id

    def _create_candidate(
        self,
        repo: SqlaCandidateRepository,
        source_id: int,
        lemma: str,
        status: CandidateStatus,
        meaning: str | None = None,
    ) -> None:
        created = repo.create_batch([
            StoredCandidate(
                source_id=source_id, lemma=lemma, pos="NOUN",
                cefr_level="B2", zipf_frequency=3.5, is_sweet_spot=True,
                context_fragment=f"context {lemma}", fragment_purity="clean",
                occurrences=1, status=status,
            )
        ])
        if meaning is not None and created[0].id is not None:
            meaning_repo = SqlaCandidateMeaningRepository(repo._session)
            meaning_repo.upsert(CandidateMeaning(
                candidate_id=created[0].id,
                meaning=meaning,
                ipa=None,
                status=EnrichmentStatus.DONE,
                error=None,
                generated_at=None,
            ))

    def test_create_batch_and_get(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        candidates = [
            StoredCandidate(
                source_id=source_id, lemma="pursuit", pos="NOUN",
                cefr_level="B2", zipf_frequency=3.5, is_sweet_spot=True,
                context_fragment="the pursuit of", fragment_purity="clean",
                occurrences=2, status=CandidateStatus.PENDING,
            ),
            StoredCandidate(
                source_id=source_id, lemma="burnout", pos="NOUN",
                cefr_level="C2", zipf_frequency=2.1, is_sweet_spot=False,
                context_fragment="leads to burnout", fragment_purity="clean",
                occurrences=1, status=CandidateStatus.PENDING,
            ),
        ]
        created = repo.create_batch(candidates)
        assert len(created) == 2
        assert all(c.id is not None for c in created)

        by_source = repo.get_by_source(source_id)
        assert len(by_source) == 2

    def test_update_status(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        created = repo.create_batch([
            StoredCandidate(
                source_id=source_id, lemma="test", pos="NOUN",
                cefr_level="B1", zipf_frequency=4.0, is_sweet_spot=True,
                context_fragment="a test", fragment_purity="clean",
                occurrences=1, status=CandidateStatus.PENDING,
            ),
        ])
        assert created[0].id is not None
        repo.update_status(created[0].id, CandidateStatus.LEARN)
        updated = repo.get_by_id(created[0].id)
        assert updated is not None
        assert updated.status == CandidateStatus.LEARN

    def test_get_nonexistent(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        assert repo.get_by_id(999) is None

    def test_get_active_without_meaning_excludes_known(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.KNOWN)
        result = repo.get_active_without_meaning(source_id=source_id, limit=10)
        assert len(result) == 0

    def test_get_active_without_meaning_excludes_skip(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.SKIP)
        result = repo.get_active_without_meaning(source_id=source_id, limit=10)
        assert len(result) == 0

    def test_get_active_without_meaning_includes_pending(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.PENDING)
        result = repo.get_active_without_meaning(source_id=source_id, limit=10)
        assert len(result) == 1
        assert result[0].lemma == "word1"

    def test_get_active_without_meaning_includes_learn(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.LEARN)
        result = repo.get_active_without_meaning(source_id=source_id, limit=10)
        assert len(result) == 1
        assert result[0].lemma == "word1"

    def test_get_active_without_meaning_excludes_with_meaning(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.PENDING, meaning="definition")
        result = repo.get_active_without_meaning(source_id=source_id, limit=10)
        assert len(result) == 0

    def test_count_active_without_meaning_excludes_known_skip(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.PENDING)
        self._create_candidate(repo, source_id, "word2", CandidateStatus.LEARN)
        self._create_candidate(repo, source_id, "word3", CandidateStatus.KNOWN)
        self._create_candidate(repo, source_id, "word4", CandidateStatus.SKIP)
        count = repo.count_active_without_meaning(source_id)
        assert count == 2

    def test_count_active_without_meaning_excludes_with_meaning(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session)
        self._create_candidate(repo, source_id, "word1", CandidateStatus.PENDING)
        self._create_candidate(repo, source_id, "word2", CandidateStatus.PENDING, meaning="definition")
        count = repo.count_active_without_meaning(source_id)
        assert count == 1


@pytest.mark.integration
class TestKnownWordRepository:
    def test_add_and_list(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session)
        kw = repo.add("run", "VERB")
        assert kw.id is not None
        assert kw.lemma == "run"
        words = repo.list_all()
        assert len(words) == 1

    def test_exists(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session)
        repo.add("run", "VERB")
        assert repo.exists("run", "VERB") is True
        assert repo.exists("run", "NOUN") is False

    def test_get_all_pairs(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session)
        repo.add("run", "VERB")
        repo.add("cat", "NOUN")
        pairs = repo.get_all_pairs()
        assert pairs == {("run", "VERB"), ("cat", "NOUN")}

    def test_remove(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session)
        kw = repo.add("run", "VERB")
        assert kw.id is not None
        repo.remove(kw.id)
        assert repo.exists("run", "VERB") is False

    def test_add_duplicate_ignored(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session)
        kw1 = repo.add("run", "VERB")
        kw2 = repo.add("run", "VERB")
        assert kw1.id == kw2.id
        assert len(repo.list_all()) == 1


@pytest.mark.integration
class TestSettingsRepository:
    def test_get_default(self, db_session: Session) -> None:
        repo = SqlaSettingsRepository(db_session)
        assert repo.get("cefr_level", "B1") == "B1"

    def test_set_and_get(self, db_session: Session) -> None:
        repo = SqlaSettingsRepository(db_session)
        repo.set("cefr_level", "C1")
        assert repo.get("cefr_level") == "C1"

    def test_set_overwrites(self, db_session: Session) -> None:
        repo = SqlaSettingsRepository(db_session)
        repo.set("cefr_level", "B1")
        repo.set("cefr_level", "C2")
        assert repo.get("cefr_level") == "C2"

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.card_choice import CardChoice, CardState
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
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
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from sqlalchemy.orm import Session

from tests.phrase_support import phrase
from tests.word_support import CardSeed, store_cards


@pytest.mark.integration
class TestSourceRepository:
    def test_create_and_get(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session))
        source = Source(
            status=SourceStatus.NEW, title="Hello", format=Format.PLAIN, kind=Kind.TEXT,
        )
        created = repo.create(source)
        assert created.id is not None
        assert created.status == SourceStatus.NEW

        fetched = repo.get_by_id(created.id)
        assert fetched is not None
        assert (fetched.title, fetched.format, fetched.kind) == ("Hello", Format.PLAIN, Kind.TEXT)

    def test_list_all(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session))
        repo.create(Source(status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT))
        repo.create(Source(status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT))
        sources = repo.list_all()
        assert len(sources) == 2

    def test_update_status(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session))
        source = repo.create(Source(
            status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT))
        assert source.id is not None
        repo.update_status(source.id, SourceStatus.DONE)
        updated = repo.get_by_id(source.id)
        assert updated is not None
        assert updated.status == SourceStatus.DONE

    def test_update_status_error(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session))
        source = repo.create(Source(
            status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT))
        assert source.id is not None
        repo.update_status(source.id, SourceStatus.ERROR, error_message="Something broke")
        updated = repo.get_by_id(source.id)
        assert updated is not None
        assert updated.status == SourceStatus.ERROR
        assert updated.error_message == "Something broke"

    def test_get_nonexistent(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session))
        assert repo.get_by_id(999) is None


@pytest.mark.integration
class TestCandidateRepository:
    def _create_source(self, db_session: Session) -> int:
        repo = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session))
        source = repo.create(Source(
            status=SourceStatus.DONE, format=Format.PLAIN, kind=Kind.TEXT))
        assert source.id is not None
        return source.id

    def _create_candidate(
        self,
        repo: SqlaCandidateRepository,
        source_id: int,
        lemma: str,
        status: WordStatus,
        meaning: str | None = None,
    ) -> None:
        created = store_cards(repo._session, [
            CardSeed(
                StoredCandidate(
                    source_id=source_id,
                    lemma=lemma,
                    pos="NOUN",
                    cefr_level="B2",
                    zipf_frequency=3.5,
                    occurrences=1,
                    status=status,
                ),
                phrase(f"context {lemma}", lemma),
            )
        ])
        if meaning is not None:
            meaning_repo = SqlaCandidateMeaningRepository(
                repo._session, SessionChangeRecorder(repo._session),
            )
            meaning_repo.upsert(CandidateMeaning(
                candidate_id=created[0].word_id,
                meaning=meaning,
                translation=None,
                synonyms=None,
                examples=None,
                ipa=None,
                generated_at=None))

    def test_create_batch_and_get(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session, SessionChangeRecorder(db_session))
        candidates = [
            CardSeed(
                StoredCandidate(
                    source_id=source_id,
                    lemma="pursuit",
                    pos="NOUN",
                    cefr_level="B2",
                    zipf_frequency=3.5,
                    occurrences=2,
                    status=WordStatus.NEW,
                ),
                phrase("the pursuit of", "pursuit"),
            ),
            CardSeed(
                StoredCandidate(
                    source_id=source_id,
                    lemma="burnout",
                    pos="NOUN",
                    cefr_level="C2",
                    zipf_frequency=2.1,
                    occurrences=1,
                    status=WordStatus.NEW,
                ),
                phrase("leads to burnout", "burnout"),
            ),
        ]
        created = store_cards(repo._session, candidates)
        assert len(created) == 2
        assert all(c.word.id is not None for c in created)

        by_source = repo.get_by_source(source_id)
        assert len(by_source) == 2

    def test_update_status(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session, SessionChangeRecorder(db_session))
        created = store_cards(repo._session, [
            CardSeed(
                StoredCandidate(
                    source_id=source_id,
                    lemma="test",
                    pos="NOUN",
                    cefr_level="B1",
                    zipf_frequency=4.0,
                    occurrences=1,
                    status=WordStatus.NEW,
                ),
                phrase("a test", "test"),
            ),
        ])
        states = SqlaWordStateRepository(db_session, SessionChangeRecorder(db_session))
        state = states.of_word(created[0].word_id)
        assert state is not None
        states.save(state.with_cards(CardState(created[0].phrase_id, CardChoice.LEARN)))
        updated = repo.get_by_id(created[0].word_id)
        assert updated is not None
        assert updated.status == WordStatus.LEARN

    def test_get_nonexistent(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session, SessionChangeRecorder(db_session))
        assert repo.get_by_id(999) is None

    def test_count_all_counts_every_status(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session, SessionChangeRecorder(db_session))
        self._create_candidate(repo, source_id, "one", WordStatus.NEW)
        self._create_candidate(repo, source_id, "two", WordStatus.LEARN)
        self._create_candidate(repo, source_id, "three", WordStatus.KNOWN)
        assert repo.count_all() == 3

    def test_a_word_is_found_by_its_key_in_its_source(self, db_session: Session) -> None:
        source_id = self._create_source(db_session)
        other_source = self._create_source(db_session)
        repo = SqlaCandidateRepository(db_session, SessionChangeRecorder(db_session))
        self._create_candidate(repo, source_id, "Glare", WordStatus.NEW)
        self._create_candidate(repo, other_source, "linger", WordStatus.NEW)
        [glare] = repo.get_by_source(source_id)

        assert repo.word_id(source_id, WordKey.of("glare", False)) == glare.id
        assert repo.word_id(source_id, WordKey.of("glare", True)) is None
        assert repo.word_id(source_id, WordKey.of("linger", False)) is None


@pytest.mark.integration
class TestKnownWordRepository:
    def test_add_and_list(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session, SessionChangeRecorder(db_session))
        kw = repo.add("run", "VERB")
        assert kw.id is not None
        assert kw.lemma == "run"
        words = repo.list_all()
        assert len(words) == 1

    def test_exists(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session, SessionChangeRecorder(db_session))
        repo.add("run", "VERB")
        assert repo.exists("run", "VERB") is True
        assert repo.exists("run", "NOUN") is False

    def test_get_all_pairs(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session, SessionChangeRecorder(db_session))
        repo.add("run", "VERB")
        repo.add("cat", "NOUN")
        pairs = repo.get_all_pairs()
        assert pairs == {("run", "VERB"), ("cat", "NOUN")}

    def test_remove(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session, SessionChangeRecorder(db_session))
        kw = repo.add("run", "VERB")
        assert kw.id is not None
        repo.remove(kw.id)
        assert repo.exists("run", "VERB") is False

    def test_add_duplicate_ignored(self, db_session: Session) -> None:
        repo = SqlaKnownWordRepository(db_session, SessionChangeRecorder(db_session))
        kw1 = repo.add("run", "VERB")
        kw2 = repo.add("run", "VERB")
        assert kw1.id == kw2.id
        assert len(repo.list_all()) == 1


@pytest.mark.integration
class TestSettingsRepository:
    def test_get_default(self, db_session: Session) -> None:
        repo = SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session))
        assert repo.get("cefr_level", "B1") == "B1"

    def test_set_and_get(self, db_session: Session) -> None:
        repo = SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session))
        repo.set("cefr_level", "C1")
        assert repo.get("cefr_level") == "C1"

    def test_set_overwrites(self, db_session: Session) -> None:
        repo = SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session))
        repo.set("cefr_level", "B1")
        repo.set("cefr_level", "C2")
        assert repo.get("cefr_level") == "C2"

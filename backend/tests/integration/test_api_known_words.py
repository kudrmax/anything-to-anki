from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import KnownWordModel
from backend.infrastructure.persistence.sqla_known_word_repository import SqlaKnownWordRepository
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine)

    # Seed
    session = test_session_factory()
    session.add(KnownWordModel(lemma="run", pos="VERB"))
    session.commit()
    session.close()

    def override_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_session_factory() -> object:
        return test_session_factory

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = override_session_factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestKnownWordsAPI:
    def test_list(self, client: TestClient) -> None:
        response = client.get("/known-words")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["lemma"] == "run"

    def test_delete(self, client: TestClient) -> None:
        response = client.delete("/known-words/1")
        assert response.status_code == 200
        response = client.get("/known-words")
        assert len(response.json()) == 0


@pytest.fixture()
def client_with_wildcard() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session_factory = sessionmaker(bind=engine)

    session = test_session_factory()
    session.add(KnownWordModel(lemma="run", pos="VERB"))
    session.add(KnownWordModel(lemma="go", pos=None))
    session.commit()
    session.close()

    def override_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    def override_session_factory() -> object:
        return test_session_factory

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = override_session_factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestKnownWordsWildcardAPI:
    def test_list_includes_wildcard(self, client_with_wildcard: TestClient) -> None:
        response = client_with_wildcard.get("/known-words")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        wildcard = [w for w in data if w["lemma"] == "go"][0]
        assert wildcard["pos"] is None

    def test_delete_wildcard(self, client_with_wildcard: TestClient) -> None:
        response = client_with_wildcard.get("/known-words")
        wildcard = [w for w in response.json() if w["lemma"] == "go"][0]
        delete_resp = client_with_wildcard.delete(f"/known-words/{wildcard['id']}")
        assert delete_resp.status_code == 200
        remaining = client_with_wildcard.get("/known-words").json()
        assert len(remaining) == 1
        assert remaining[0]["lemma"] == "run"


@pytest.mark.integration
class TestKnownWordRepoWildcard:
    def _make_repo(self) -> tuple[SqlaKnownWordRepository, Session]:
        engine = create_engine("sqlite:///:memory:", poolclass=StaticPool)
        Base.metadata.create_all(engine)
        session = Session(bind=engine)
        return SqlaKnownWordRepository(session), session

    def test_add_wildcard(self) -> None:
        repo, _ = self._make_repo()
        result = repo.add("run", None)
        assert result.lemma == "run"
        assert result.pos is None

    def test_add_wildcard_idempotent(self) -> None:
        repo, _ = self._make_repo()
        first = repo.add("run", None)
        second = repo.add("run", None)
        assert first.id == second.id
        assert repo.count() == 1

    def test_exists_wildcard(self) -> None:
        repo, _ = self._make_repo()
        repo.add("run", None)
        assert repo.exists("run", None) is True
        assert repo.exists("run", "VERB") is False

    def test_get_all_pairs_includes_wildcard(self) -> None:
        repo, _ = self._make_repo()
        repo.add("run", "VERB")
        repo.add("go", None)
        pairs = repo.get_all_pairs()
        assert ("run", "VERB") in pairs
        assert ("go", None) in pairs

    def test_exact_and_wildcard_coexist(self) -> None:
        repo, _ = self._make_repo()
        repo.add("run", "VERB")
        repo.add("run", None)
        assert repo.count() == 2
        assert repo.exists("run", "VERB") is True
        assert repo.exists("run", None) is True

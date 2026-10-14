from __future__ import annotations

import pytest
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.mark.integration
def test_counts_candidates_by_source_and_status() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    rows = [(1, 1, "pending"), (2, 1, "learn"), (3, 1, "learn"), (4, 2, "known")]
    for cid, source_id, status in rows:
        session.execute(
            text(
                "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, "
                "is_sweet_spot, context_fragment, fragment_purity, occurrences, status, "
                "is_phrasal_verb, has_custom_context_fragment) "
                f"VALUES ({cid}, {source_id}, 'w{cid}', 'NOUN', 3.0, 0, 'x', 'clean', 1, "
                f"'{status}', 0, 0)"
            )
        )
    session.commit()

    counts = SqlaCandidateRepository(session).count_by_source_and_status()

    assert counts == {
        1: {CandidateStatus.PENDING: 1, CandidateStatus.LEARN: 2},
        2: {CandidateStatus.KNOWN: 1},
    }

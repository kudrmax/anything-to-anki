from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.models import EnrichmentCacheModel
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_enrichment_cache_repository import (
    SqlaEnrichmentCacheRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _create_source_with_enriched_candidates(db_session: Session) -> int:
    """Create a DONE source with 2 candidates, each having full enrichment."""
    source_repo = SqlaSourceRepository(db_session)
    candidate_repo = SqlaCandidateRepository(db_session)
    meaning_repo = SqlaCandidateMeaningRepository(db_session)
    media_repo = SqlaCandidateMediaRepository(db_session)
    pronunciation_repo = SqlaCandidatePronunciationRepository(db_session)
    tts_repo = SqlaCandidateTTSRepository(db_session)

    source = source_repo.create(
        Source(
            raw_text="She tends to procrastinate when facing deadlines.",
            status=SourceStatus.DONE,
            input_method=InputMethod.TEXT_PASTED,
            content_type=ContentType.TEXT,
            cleaned_text="She tends to procrastinate when facing deadlines.",
        )
    )
    assert source.id is not None

    now = datetime.now(tz=UTC)
    candidates = candidate_repo.create_batch(
        [
            StoredCandidate(
                source_id=source.id,
                lemma="procrastinate",
                pos="VERB",
                cefr_level="C1",
                zipf_frequency=3.2,
                context_fragment="She tends to procrastinate when facing deadlines.",
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.LEARN,
            ),
            StoredCandidate(
                source_id=source.id,
                lemma="deadline",
                pos="NOUN",
                cefr_level="B2",
                zipf_frequency=4.5,
                context_fragment="She tends to procrastinate when facing deadlines.",
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.LEARN,
            ),
        ]
    )

    for c in candidates:
        assert c.id is not None
        meaning_repo.upsert(
            CandidateMeaning(
                candidate_id=c.id,
                meaning=f"meaning of {c.lemma}",
                translation=f"перевод {c.lemma}",
                synonyms=f"syn of {c.lemma}",
                examples=f"ex of {c.lemma}",
                ipa=f"/ipa-{c.lemma}/",
                generated_at=now,
            )
        )
        media_repo.upsert(
            CandidateMedia(
                candidate_id=c.id,
                screenshot_path=f"/media/{source.id}/{c.id}_screenshot.jpg",
                audio_path=f"/media/{source.id}/{c.id}_audio.mp3",
                start_ms=1000,
                end_ms=5000,
                generated_at=now,
            )
        )
        pronunciation_repo.upsert(
            CandidatePronunciation(
                candidate_id=c.id,
                us_audio_path=f"/pron/{c.lemma}_us.mp3",
                uk_audio_path=f"/pron/{c.lemma}_uk.mp3",
                generated_at=now,
            )
        )
        tts_repo.upsert(
            CandidateTTS(
                candidate_id=c.id,
                audio_path=f"/tts/{c.id}_tts.mp3",
                generated_at=now,
            )
        )

    db_session.flush()
    return source.id


def _create_source_with_enriched_candidates_v2(
    db_session: Session, text: str, lemma1: str, lemma2: str
) -> int:
    """Create a DONE source with 2 candidates having different lemmas but same fragment."""
    source_repo = SqlaSourceRepository(db_session)
    candidate_repo = SqlaCandidateRepository(db_session)
    meaning_repo = SqlaCandidateMeaningRepository(db_session)
    media_repo = SqlaCandidateMediaRepository(db_session)
    pronunciation_repo = SqlaCandidatePronunciationRepository(db_session)
    tts_repo = SqlaCandidateTTSRepository(db_session)

    source = source_repo.create(
        Source(
            raw_text=text,
            status=SourceStatus.DONE,
            input_method=InputMethod.TEXT_PASTED,
            content_type=ContentType.TEXT,
            cleaned_text=text,
        )
    )
    assert source.id is not None

    now = datetime.now(tz=UTC)
    candidates = candidate_repo.create_batch(
        [
            StoredCandidate(
                source_id=source.id,
                lemma=lemma1,
                pos="VERB",
                cefr_level="C1",
                zipf_frequency=3.2,
                context_fragment=text,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.LEARN,
            ),
            StoredCandidate(
                source_id=source.id,
                lemma=lemma2,
                pos="NOUN",
                cefr_level="B2",
                zipf_frequency=4.5,
                context_fragment=text,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.LEARN,
            ),
        ]
    )

    for c in candidates:
        assert c.id is not None
        meaning_repo.upsert(
            CandidateMeaning(
                candidate_id=c.id,
                meaning=f"meaning of {c.lemma}",
                translation=f"перевод {c.lemma}",
                synonyms=f"syn of {c.lemma}",
                examples=f"ex of {c.lemma}",
                ipa=f"/ipa-{c.lemma}/",
                generated_at=now,
            )
        )
        media_repo.upsert(
            CandidateMedia(
                candidate_id=c.id,
                screenshot_path=f"/media/{source.id}/{c.id}_screenshot.jpg",
                audio_path=f"/media/{source.id}/{c.id}_audio.mp3",
                start_ms=1000,
                end_ms=5000,
                generated_at=now,
            )
        )
        pronunciation_repo.upsert(
            CandidatePronunciation(
                candidate_id=c.id,
                us_audio_path=f"/pron/{c.lemma}_us.mp3",
                uk_audio_path=f"/pron/{c.lemma}_uk.mp3",
                generated_at=now,
            )
        )
        tts_repo.upsert(
            CandidateTTS(
                candidate_id=c.id,
                audio_path=f"/tts/{c.id}_tts.mp3",
                generated_at=now,
            )
        )

    db_session.flush()
    return source.id


@pytest.mark.integration
def test_save_from_source_populates_cache(db_session: Session) -> None:
    source_id = _create_source_with_enriched_candidates(db_session)
    cache_repo = SqlaEnrichmentCacheRepository(db_session)

    cache_repo.save_from_source(source_id)

    rows = db_session.query(EnrichmentCacheModel).filter_by(source_id=source_id).all()
    assert len(rows) == 2

    by_lemma = {r.lemma: r for r in rows}
    proc = by_lemma["procrastinate"]
    assert proc.meaning == "meaning of procrastinate"
    assert proc.translation == "перевод procrastinate"
    assert proc.ipa == "/ipa-procrastinate/"
    assert proc.screenshot_path is not None
    assert proc.us_audio_path is not None
    assert proc.tts_audio_path is not None
    assert proc.meaning_generated_at is not None
    assert proc.media_generated_at is not None
    assert proc.pronunciation_generated_at is not None
    assert proc.tts_generated_at is not None


@pytest.mark.integration
def test_restore_to_candidates_after_reprocess(db_session: Session) -> None:
    fragment = "She tends to procrastinate when facing deadlines."
    source_id = _create_source_with_enriched_candidates(db_session)
    cache_repo = SqlaEnrichmentCacheRepository(db_session)
    candidate_repo = SqlaCandidateRepository(db_session)
    meaning_repo = SqlaCandidateMeaningRepository(db_session)
    media_repo = SqlaCandidateMediaRepository(db_session)
    pronunciation_repo = SqlaCandidatePronunciationRepository(db_session)
    tts_repo = SqlaCandidateTTSRepository(db_session)

    cache_repo.save_from_source(source_id)
    candidate_repo.delete_by_source(source_id)
    db_session.flush()

    # Recreate with same (lemma, pos, context_fragment) but different CEFR
    new_candidates = candidate_repo.create_batch(
        [
            StoredCandidate(
                source_id=source_id,
                lemma="procrastinate",
                pos="VERB",
                cefr_level="C2",  # changed from C1
                zipf_frequency=3.2,
                context_fragment=fragment,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
            StoredCandidate(
                source_id=source_id,
                lemma="deadline",
                pos="NOUN",
                cefr_level="B1",  # changed from B2
                zipf_frequency=4.5,
                context_fragment=fragment,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
        ]
    )
    db_session.flush()

    restored = cache_repo.restore_to_candidates(source_id)
    assert restored == 2

    for c in new_candidates:
        assert c.id is not None
        m = meaning_repo.get_by_candidate_id(c.id)
        assert m is not None
        assert m.meaning == f"meaning of {c.lemma}"

        med = media_repo.get_by_candidate_id(c.id)
        assert med is not None
        assert med.screenshot_path is not None

        pron = pronunciation_repo.get_by_candidate_id(c.id)
        assert pron is not None
        assert pron.us_audio_path == f"/pron/{c.lemma}_us.mp3"

        tts = tts_repo.get_by_candidate_id(c.id)
        assert tts is not None
        assert tts.audio_path is not None


@pytest.mark.integration
def test_no_restore_when_fragment_changed(db_session: Session) -> None:
    source_id = _create_source_with_enriched_candidates(db_session)
    cache_repo = SqlaEnrichmentCacheRepository(db_session)
    candidate_repo = SqlaCandidateRepository(db_session)
    meaning_repo = SqlaCandidateMeaningRepository(db_session)

    cache_repo.save_from_source(source_id)

    # Add a brand-new candidate with a different fragment (never existed before).
    # We do NOT delete old candidates — we just add a new one with a changed fragment
    # and verify restore_to_candidates does not match it.
    new_candidates = candidate_repo.create_batch(
        [
            StoredCandidate(
                source_id=source_id,
                lemma="procrastinate",
                pos="VERB",
                cefr_level="C1",
                zipf_frequency=3.2,
                context_fragment="People often procrastinate on difficult tasks.",
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
        ]
    )
    db_session.flush()

    # Cache was built before this candidate existed — its fragment differs from cached one.
    # restore_to_candidates matches on (lemma, pos, context_fragment), so this candidate
    # must NOT be matched (context_fragment changed).
    # Count only newly restored: we check the new candidate specifically.
    cache_repo.restore_to_candidates(source_id)

    assert new_candidates[0].id is not None
    m = meaning_repo.get_by_candidate_id(new_candidates[0].id)
    # The new candidate has a different context_fragment — no cache hit, so meaning
    # must not have been written for its id.
    assert m is None


@pytest.mark.integration
def test_cleanup_removes_cache_for_source(db_session: Session) -> None:
    source_id = _create_source_with_enriched_candidates(db_session)
    cache_repo = SqlaEnrichmentCacheRepository(db_session)

    cache_repo.save_from_source(source_id)

    rows_before = (
        db_session.query(EnrichmentCacheModel).filter_by(source_id=source_id).all()
    )
    assert len(rows_before) == 2

    cache_repo.cleanup(source_id)

    rows_after = (
        db_session.query(EnrichmentCacheModel).filter_by(source_id=source_id).all()
    )
    assert len(rows_after) == 0


@pytest.mark.integration
def test_parallel_reprocess_two_sources(db_session: Session) -> None:
    fragment1 = "She tends to procrastinate when facing deadlines."
    fragment2 = "He always perseveres through tough challenges."

    source_id1 = _create_source_with_enriched_candidates_v2(
        db_session, fragment1, "procrastinate", "deadline"
    )
    source_id2 = _create_source_with_enriched_candidates_v2(
        db_session, fragment2, "persevere", "challenge"
    )

    cache_repo = SqlaEnrichmentCacheRepository(db_session)
    candidate_repo = SqlaCandidateRepository(db_session)
    meaning_repo = SqlaCandidateMeaningRepository(db_session)

    cache_repo.save_from_source(source_id1)
    cache_repo.save_from_source(source_id2)

    candidate_repo.delete_by_source(source_id1)
    candidate_repo.delete_by_source(source_id2)
    db_session.flush()

    new1 = candidate_repo.create_batch(
        [
            StoredCandidate(
                source_id=source_id1,
                lemma="procrastinate",
                pos="VERB",
                cefr_level="C1",
                zipf_frequency=3.2,
                context_fragment=fragment1,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
            StoredCandidate(
                source_id=source_id1,
                lemma="deadline",
                pos="NOUN",
                cefr_level="B2",
                zipf_frequency=4.5,
                context_fragment=fragment1,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
        ]
    )
    new2 = candidate_repo.create_batch(
        [
            StoredCandidate(
                source_id=source_id2,
                lemma="persevere",
                pos="VERB",
                cefr_level="B2",
                zipf_frequency=3.8,
                context_fragment=fragment2,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
            StoredCandidate(
                source_id=source_id2,
                lemma="challenge",
                pos="NOUN",
                cefr_level="B1",
                zipf_frequency=4.9,
                context_fragment=fragment2,
                fragment_purity="pure",
                occurrences=1,
                status=CandidateStatus.PENDING,
            ),
        ]
    )
    db_session.flush()

    restored1 = cache_repo.restore_to_candidates(source_id1)
    restored2 = cache_repo.restore_to_candidates(source_id2)
    assert restored1 == 2
    assert restored2 == 2

    # Source 1 gets its own enrichments
    for c in new1:
        assert c.id is not None
        m = meaning_repo.get_by_candidate_id(c.id)
        assert m is not None
        assert m.meaning == f"meaning of {c.lemma}"

    # Source 2 gets its own enrichments
    for c in new2:
        assert c.id is not None
        m = meaning_repo.get_by_candidate_id(c.id)
        assert m is not None
        assert m.meaning == f"meaning of {c.lemma}"

    # Source 1 did NOT get source 2 enrichments (cross-contamination check)
    for c in new1:
        assert c.id is not None
        m = meaning_repo.get_by_candidate_id(c.id)
        assert m is not None
        assert c.lemma in m.meaning

    cache_repo.cleanup(source_id1)
    cache_repo.cleanup(source_id2)

    assert (
        len(
            db_session.query(EnrichmentCacheModel).filter_by(source_id=source_id1).all()
        )
        == 0
    )
    assert (
        len(
            db_session.query(EnrichmentCacheModel).filter_by(source_id=source_id2).all()
        )
        == 0
    )


@pytest.mark.integration
def test_cleanup_all(db_session: Session) -> None:
    source_id1 = _create_source_with_enriched_candidates(db_session)
    source_id2 = _create_source_with_enriched_candidates_v2(
        db_session,
        "He always perseveres through tough challenges.",
        "persevere",
        "challenge",
    )
    cache_repo = SqlaEnrichmentCacheRepository(db_session)

    cache_repo.save_from_source(source_id1)
    cache_repo.save_from_source(source_id2)

    rows_before = db_session.query(EnrichmentCacheModel).all()
    assert len(rows_before) >= 4  # at least 2 per source

    cache_repo.cleanup_all()

    rows_after = db_session.query(EnrichmentCacheModel).all()
    assert len(rows_after) == 0

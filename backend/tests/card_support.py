"""Cards of the review list for tests: a word and one of its phrases."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.review_card import ReviewCard
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.application.utils.card_views import CardViews
    from backend.domain.value_objects.elsewhere import Elsewhere
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.orm import Session


def word(
    word_id: int = 1, lemma: str = "test", *, status: WordStatus = WordStatus.PENDING,
    **changes: object,
) -> StoredCandidate:
    """A pending word of source 10; its card-shaped phrase fields are not read by cards."""
    made = StoredCandidate(
        id=word_id, source_id=10, lemma=lemma, pos="NOUN", cefr_level="B2",
        zipf_frequency=3.5, source_phrase=phrase(f"a {lemma}", lemma), occurrences=1,
        status=CandidateStatus(status.value),
    )
    return replace(made, **changes)  # type: ignore[arg-type]


def occurrence(
    phrase_id: int = 1, word_id: int = 1, text: Phrase | None = None, **changes: object,
) -> Occurrence:
    """A shown auto phrase of the word."""
    made = Occurrence(
        id=phrase_id, candidate_id=word_id, origin=OccurrenceOrigin.AUTO,
        source_phrase=text or phrase("a test", "test"), phrase_position=None, key=None,
        fragment_score=None, shown_by=ShownBy.SELECTION,
    )
    return replace(made, **changes)  # type: ignore[arg-type]


def card(
    the_word: StoredCandidate | None = None,
    the_occurrence: Occurrence | None = None,
    *,
    elsewhere: Elsewhere | None = None,
) -> ReviewCard:
    w = the_word or word()
    assert w.id is not None
    occ = the_occurrence or occurrence(word_id=w.id)
    return ReviewCard(
        word=w, occurrence=occ, word_status=WordStatus(
            w.status.value if w.status is not CandidateStatus.SKIP else "pending",
        ),
        elsewhere=elsewhere,
    )


def card_views(session: Session) -> CardViews:
    """Real card views over the database; the user knows no words."""
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.decided_elsewhere import DecidedElsewhere
    from backend.application.utils.review_cards import ReviewCards
    from backend.infrastructure.persistence.sqla_candidate_repository import (
        SqlaCandidateRepository,
    )
    from backend.infrastructure.persistence.sqla_card_report_repository import (
        SqlaCardReportRepository,
    )
    from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
    from backend.infrastructure.persistence.sqla_occurrence_repository import (
        SqlaOccurrenceRepository,
    )
    from backend.infrastructure.persistence.sqla_settings_repository import (
        SqlaSettingsRepository,
    )

    from tests.candidate_sorter_support import candidate_sorter
    from tests.vocabulary_support import user_vocabulary

    return CardViews(
        review_cards=ReviewCards(
            SqlaCandidateRepository(session), SqlaOccurrenceRepository(session),
            DecidedElsewhere(user_vocabulary()),
        ),
        candidate_sorter=candidate_sorter(SqlaSettingsRepository(session)),
        job_repo=SqlaJobRepository(session),
        report_repo=SqlaCardReportRepository(session),
    )

"""Cards of the review list for tests: a word and one of its phrases."""
from __future__ import annotations

from collections.abc import Iterator  # noqa: TC003 — used at runtime by @contextmanager
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import CardSourceDTO
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.ports.word_state_repository import WordStateRepository
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    WordState,
)
from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.review_card import CardContext, ReviewCard
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder

from tests.decision_support import NOW
from tests.phrase_support import phrase
from tests.source_order_support import added_order

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterable
    from datetime import datetime

    from backend.application.utils.card_views import CardViews
    from backend.domain.value_objects.elsewhere import ElsewhereStatus
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.orm import Session


# The source of `word`'s cards as a card shows it.
CARD_SOURCE = CardSourceDTO(id=10, has_video=False, can_polish_phrases=False)


def word(
    word_id: int = 1, lemma: str = "test", *, status: WordStatus = WordStatus.NEW,
    **changes: object,
) -> StoredCandidate:
    """A word of source 10, pending unless `status` says otherwise."""
    made = StoredCandidate(
        id=word_id, source_id=10, lemma=lemma, pos="NOUN", cefr_level="B2",
        zipf_frequency=3.5, occurrences=1, status=status,
    )
    return replace(made, **changes)  # type: ignore[arg-type]


def occurrence(
    phrase_id: int = 1, word_id: int = 1, text: Phrase | None = None, *,
    skipped: bool = False, is_decision: bool = False,
    decision_kind: DecisionKind | None = None, exported: bool = False, **changes: object,
) -> Occurrence:
    """A shown auto phrase of the word. Shorthands for its choice and binding: `skipped`,
    `is_decision` (a Learn, or `decision_kind`), and `exported` (the decision card bound to
    a note of its kind, exported a day before the tests' moment)."""
    decided = is_decision or exported
    choice = (
        CardChoice.CLOZE if decision_kind is DecisionKind.CLOZE else CardChoice.LEARN
    ) if decided else CardChoice.SKIP if skipped else CardChoice.NONE
    kind = NoteKind.CLOZE if choice is CardChoice.CLOZE else NoteKind.LEARN
    made = Occurrence(
        id=phrase_id, candidate_id=word_id, origin=OccurrenceOrigin.AUTO,
        source_phrase=text or phrase("a test", "test"), phrase_position=None, key=None,
        fragment_score=None,
        earned_section=CandidateSection.READY, shown_by=ShownBy.SELECTION, choice=choice,
        binding=Binding(kind, NOW - timedelta(days=1)) if exported else None,
    )
    return replace(made, **changes)  # type: ignore[arg-type]


# The id of the card holding a decided word's decision when the card under test does not.
DECISION_CARD_ID = 999_999


def context(
    the_word: StoredCandidate, *occurrences: Occurrence, known_marked: bool | None = None,
    unknown: bool = False, now: datetime = NOW,
) -> CardContext:
    """The word as the decision tables see it: these cards, plus a decision card for a word
    decided but on none of them, as its status says. Known is listed for a Known word unless
    `known_marked` says otherwise."""
    assert the_word.id is not None
    cards = [occ.card_state for occ in occurrences]
    if the_word.status is not WordStatus.NEW and not any(c.is_decision for c in cards):
        cards.append(CardState(DECISION_CARD_ID, *_DECISION_OF_STATUS[the_word.status]))
    since = tuple(c.binding.learning_since for c in cards if c.binding is not None)
    knowledge = LemmaKnowledge.at(
        now,
        known_marked=the_word.status is WordStatus.KNOWN if known_marked is None else known_marked,
        unknown=unknown, learn_anywhere=False, active_since=since,
    )
    state = WordState(
        the_word.id, the_word.lemma, the_word.pos, the_word.source_id, tuple(cards),
    )
    return CardContext(word=state, knowledge=knowledge, now=now)


_DECISION_OF_STATUS: dict[WordStatus, tuple[CardChoice, Binding | None]] = {
    WordStatus.LEARN: (CardChoice.LEARN, None),
    WordStatus.LEARNING: (CardChoice.LEARN, Binding(NoteKind.LEARN, NOW)),
    WordStatus.KNOWN: (CardChoice.KNOWN, None),
}


def card(
    the_word: StoredCandidate | None = None,
    the_occurrence: Occurrence | None = None,
    *,
    elsewhere: ElsewhereStatus | None = None,
    known_marked: bool | None = None,
) -> ReviewCard:
    w = the_word or word()
    assert w.id is not None
    occ = the_occurrence or occurrence(word_id=w.id)
    return ReviewCard(
        word=w, occurrence=occ, elsewhere=elsewhere,
        context=context(w, occ, known_marked=known_marked),
    )


def card_views(session: Session) -> CardViews:
    """Real card views over the database; the user knows no words."""
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.review_cards import ReviewCards
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.infrastructure.persistence.sqla_candidate_repository import (
        SqlaCandidateRepository,
    )
    from backend.infrastructure.persistence.sqla_card_report_repository import (
        SqlaCardReportRepository,
    )
    from backend.infrastructure.persistence.sqla_collection_repository import (
        SqlaCollectionRepository,
    )
    from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
    from backend.infrastructure.persistence.sqla_occurrence_repository import (
        SqlaOccurrenceRepository,
    )
    from backend.infrastructure.persistence.sqla_settings_repository import (
        SqlaSettingsRepository,
    )
    from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
    from backend.infrastructure.persistence.sqla_word_state_repository import (
        SqlaWordStateRepository,
    )

    from tests.candidate_sorter_support import candidate_sorter
    from tests.vocabulary_support import user_vocabulary

    vocabulary = user_vocabulary()
    return CardViews(
        review_cards=ReviewCards(
            SqlaCandidateRepository(session, SessionChangeRecorder(session)),
            SqlaOccurrenceRepository(session, SessionChangeRecorder(session)),
            SqlaWordStateRepository(session, SessionChangeRecorder(session)), vocabulary,
        ),
        candidate_sorter=candidate_sorter(SqlaSettingsRepository(
            session, SessionChangeRecorder(session),
        )),
        job_repo=SqlaJobRepository(session),
        report_repo=SqlaCardReportRepository(session),
        scope_resolver=SourceScopeResolver(
            SqlaSourceRepository(session, SessionChangeRecorder(session)),
            SqlaCollectionRepository(session),
            added_order(),
        ),
        source_repo=SqlaSourceRepository(session, SessionChangeRecorder(session)),
    )


class PhraseWordStates(WordStateRepository):
    """Word states made from the words and phrases a test feeds its mocks: every phrase
    given is a card of its word (`context`). Nothing is written."""

    def __init__(
        self,
        words: Callable[[], Iterable[StoredCandidate]],
        phrases: Callable[[int], Iterable[Occurrence]],
    ) -> None:
        self._words = words
        self._phrases = phrases

    def of_word(self, word_id: int) -> WordState | None:
        found = next((w for w in self._words() if w.id == word_id), None)
        return None if found is None else context(found, *self._phrases(word_id)).word

    def of_source(self, source_id: int) -> dict[int, WordState]:
        """The words given are the source's."""
        del source_id
        return {
            w.id: context(w, *self._phrases(w.id)).word
            for w in self._words() if w.id is not None
        }

    def of_words(self, word_ids: Collection[int]) -> dict[int, WordState]:
        return {
            w.id: context(w, *self._phrases(w.id)).word
            for w in self._words() if w.id is not None and w.id in word_ids
        }

    @contextmanager
    def batch(self) -> Iterator[None]:
        yield

    def of_lemma(self, lemma: str) -> list[WordState]:
        return [
            context(w, *self._phrases(w.id)).word
            for w in self._words() if w.lemma.lower() == lemma.lower() and w.id is not None
        ]

    def of_lemmas(self, lemmas: Collection[str]) -> dict[int, WordState]:
        keys = {lemma.lower() for lemma in lemmas}
        return {
            w.id: context(w, *self._phrases(w.id)).word
            for w in self._words() if w.lemma.lower() in keys and w.id is not None
        }

    def save(self, word: WordState) -> None:
        raise AssertionError("these word states are read only")

"""A topic source collects real phrases from the other sources, offline.

Real spaCy, dictionaries and SQLite: targets are stored as if AI had already
generated them, then processing runs without AI. Topics are not rebuilt: a refresh
adds the phrases later sources give their targets, and changes nothing the topic has.
"""
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.constants import FREQUENT_WORD_THRESHOLD_SETTING
from backend.application.use_cases.refresh_topic import RefreshTopicUseCase
from backend.application.utils.collected_phrases import CollectedPhrases
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.topic_target import TopicTarget
from backend.domain.exceptions import (
    RefreshNotSupportedError,
    TopicTargetsMissingError,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.phrase_origin import PhraseOrigin
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)
from backend.infrastructure.persistence.sqla_word_mark_repository import (
    SqlaWordMarkRepository,
)
from sqlalchemy import text

from tests.candidate_sorter_support import section_stamper
from tests.phrase_support import phrase
from tests.word_support import store_card

if TYPE_CHECKING:
    from backend.application.dto.rebuild_dtos import TopicRefreshSummaryDTO
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.new_card import NewCard
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

NOVEL_TEXT = "It was late. In the end we agreed to meet halfway on the price."
MEMOIR_FRAGMENT = "He refused to negotiate with them."
LATER_ARTICLE = "The company answered with a counter-offer the next morning."
ANOTHER_ARTICLE = "Their rivals made a counter-offer within the hour."


def _add_source(
    session: Session,
    title: str,
    kind: Kind | None,
    text: str,
    status: SourceStatus = SourceStatus.DONE,
) -> int:
    """Content with a one-paragraph document, or a topic (no kind) asking for `text`."""
    source = SqlaSourceRepository(session, SessionChangeRecorder(session)).create(
        Source(
            title=title,
            status=status,
            kind=kind,
            role=SourceRole.CONTENT if kind else SourceRole.TOPIC,
            topic_query=None if kind else text,
        ),
    )
    assert source.id is not None
    if kind is not None:
        SqlaDocumentRepository(session).save(
            source.id,
            Document((Paragraph(lines=(Line(text),), mode=ParagraphMode.FLOW),)),
        )
    session.commit()
    return source.id


def _add_memoir_with_candidate(session: Session) -> None:
    memoir_id = _add_source(
        session, "Memoir", Kind.TEXT, MEMOIR_FRAGMENT,
    )
    store_card(session, StoredCandidate(
        source_id=memoir_id,
        lemma="negotiate",
        pos="VERB",
        cefr_level="B2",
        zipf_frequency=3.6,
        occurrences=1,
        status=WordStatus.NEW,
    ), phrase(MEMOIR_FRAGMENT, "negotiate"))


def _add_topic(session: Session) -> int:
    topic_id = _add_source(
        session, "Salary talk", None, "negotiating a salary",
        status=SourceStatus.NEW,
    )
    examples = [
        ("negotiate", "We had to **negotiate** a better deal."),
        ("meet halfway", "Let's **meet halfway** on this one."),
        ("counter-offer", "They sent a **counter-offer** at once."),
        ("salary", "My **salary** is paid every month."),
    ]
    SqlaTopicTargetRepository(session).create_batch([
        TopicTarget(source_id=topic_id, position=i, phrase=target, example=example)
        for i, (target, example) in enumerate(examples)
    ])
    session.commit()
    return topic_id


def _by_lemma(session: Session, source_id: int) -> dict[str, Occurrence]:
    """The first shown phrase of each word of the source."""
    occurrences = SqlaOccurrenceRepository(session, SessionChangeRecorder(session))
    lemmas = {w.id: w.lemma for w in occurrences.word_rows(source_id)}
    shown: dict[str, Occurrence] = {}
    for occ in occurrences.by_source(source_id):
        if occ.is_shown:
            shown.setdefault(lemmas[occ.candidate_id], occ)
    return shown


@pytest.fixture()
def container() -> Container:
    return Container()


def test_topic_borrows_phrases_and_falls_back_to_generated(
    db_session: Session, container: Container,
) -> None:
    _add_source(
        db_session, "Novel", Kind.TEXT, NOVEL_TEXT, status=SourceStatus.NEW,
    )
    _add_memoir_with_candidate(db_session)
    # Not processed yet: its document is read already, so the topic finds it too
    _add_source(
        db_session, "Subtitles", Kind.SUBTITLES, LATER_ARTICLE,
        status=SourceStatus.NEW,
    )
    marks = SqlaWordMarkRepository(db_session, SessionChangeRecorder(db_session))
    marks.mark_known("salary", "NOUN")
    topic_id = _add_topic(db_session)

    container.process_source_use_case(db_session).run([topic_id])

    candidates = _by_lemma(db_session, topic_id)
    assert set(candidates) == {"negotiate", "meet halfway", "counter-offer"}

    negotiate = candidates["negotiate"]
    assert negotiate.source_phrase.text == MEMOIR_FRAGMENT
    assert negotiate.source_phrase.target_text() == "negotiate"
    assert negotiate.collected_from == PhraseOrigin.from_source("Memoir")

    meet_halfway = candidates["meet halfway"]
    assert meet_halfway.source_phrase.text == "In the end we agreed to meet halfway on the price."
    assert meet_halfway.source_phrase.target_text() == "meet halfway"
    assert meet_halfway.collected_from == PhraseOrigin.from_source("Novel")

    counter_offer = candidates["counter-offer"]
    assert counter_offer.source_phrase.text == LATER_ARTICLE
    assert counter_offer.source_phrase.target_text() == "counter-offer"
    assert counter_offer.collected_from == PhraseOrigin.from_source("Subtitles")

    topic = SqlaSourceRepository(db_session, SessionChangeRecorder(db_session)).get_by_id(topic_id)
    assert topic is not None
    assert topic.status == SourceStatus.DONE


def _processed_topic(db_session: Session, container: Container) -> int:
    topic_id = _add_topic(db_session)
    container.process_source_use_case(db_session).run([topic_id])
    return topic_id


def _texts(db_session: Session, topic_id: int, lemma: str) -> list[str]:
    word_ids = {w.lemma: w.id for w in SqlaOccurrenceRepository(
        db_session, SessionChangeRecorder(db_session),
    ).word_rows(topic_id)}
    return [
        o.source_phrase.text
        for o in SqlaOccurrenceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).by_source(topic_id)
        if o.candidate_id == word_ids[lemma]
    ]


def test_a_real_phrase_is_added_beside_an_untouched_generated_one(
    db_session: Session, container: Container,
) -> None:
    topic_id = _processed_topic(db_session, container)
    [generated] = _texts(db_session, topic_id, "counter-offer")
    assert _by_lemma(db_session, topic_id)["counter-offer"].collected_from == (
        PhraseOrigin.generated()
    )

    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    summary = container.refresh_topic_use_case(db_session).execute(topic_id)

    assert (summary.words_added, summary.phrases_added) == (0, 1)
    assert _texts(db_session, topic_id, "counter-offer") == [generated, LATER_ARTICLE]
    [added] = [
        o for o in SqlaOccurrenceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).by_source(topic_id)
        if o.source_phrase.text == LATER_ARTICLE
    ]
    assert added.origin is OccurrenceOrigin.COLLECTED
    assert added.collected_from == PhraseOrigin.from_source("Article")
    assert added.shown_by is not None


def test_a_generated_phrase_with_generation_stays_beside_the_real_one(
    db_session: Session, container: Container,
) -> None:
    topic_id = _processed_topic(db_session, container)
    occurrences = SqlaOccurrenceRepository(db_session, SessionChangeRecorder(db_session))
    word_ids = {w.lemma: w.id for w in occurrences.word_rows(topic_id)}
    [generated] = [
        o for o in occurrences.by_source(topic_id) if o.candidate_id == word_ids["counter-offer"]
    ]
    _give_meaning(db_session, generated.id, generated.candidate_id)

    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    summary = container.refresh_topic_use_case(db_session).execute(topic_id)

    assert summary.phrases_added == 1
    shown = [
        o.source_phrase.text for o in occurrences.by_source(topic_id)
        if o.candidate_id == word_ids["counter-offer"] and o.shown_by is not None
    ]
    assert shown == [generated.source_phrase.text, LATER_ARTICLE]
    kept = occurrences.get(generated.id)
    assert kept is not None
    assert kept.meaning is not None


def _give_meaning(db_session: Session, phrase_id: int, word_id: int) -> None:
    SqlaCandidateMeaningRepository(
        db_session, SessionChangeRecorder(db_session),
    ).upsert_for_phrase(phrase_id, CandidateMeaning(
        candidate_id=word_id, meaning="a reply offer", translation=None,
        synonyms=None, examples=None, ipa=None, generated_at=None,
    ))
    db_session.commit()


def test_refreshing_keeps_decisions_and_results(
    db_session: Session, container: Container,
) -> None:
    topic_id = _processed_topic(db_session, container)
    occurrences = SqlaOccurrenceRepository(db_session, SessionChangeRecorder(db_session))
    before = {o.id: o for o in occurrences.by_source(topic_id)}
    word_ids = {w.lemma: w.id for w in occurrences.word_rows(topic_id)}
    decided = next(o for o in before.values() if o.candidate_id == word_ids["counter-offer"])
    db_session.execute(
        text("UPDATE phrases SET choice = 'learn' WHERE id = :id"), {"id": decided.id},
    )
    db_session.expire_all()
    _give_meaning(db_session, decided.id, decided.candidate_id)
    before = {o.id: o for o in occurrences.by_source(topic_id)}

    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)

    after = {o.id: o for o in occurrences.by_source(topic_id)}
    assert {i: after[i] for i in before} == before
    [word] = [w for w in occurrences.word_rows(topic_id) if w.lemma == "counter-offer"]
    assert word.status is WordStatus.LEARN


def test_topic_and_refresh_phrases_are_stamped(
    db_session: Session, container: Container,
) -> None:
    SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session)).set(
        FREQUENT_WORD_THRESHOLD_SETTING, "5.0",
    )
    topic_id = _processed_topic(db_session, container)
    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)

    stored = SqlaOccurrenceRepository(
        db_session, SessionChangeRecorder(db_session),
    ).by_source(topic_id)
    assert len(stored) > 1
    assert all(o.earned_section is CandidateSection.READY for o in stored)


def test_a_real_phrase_added_beside_a_generated_one_is_never_replaced(
    db_session: Session, container: Container,
) -> None:
    topic_id = _processed_topic(db_session, container)
    occurrences = SqlaOccurrenceRepository(db_session, SessionChangeRecorder(db_session))
    word_ids = {w.lemma: w.id for w in occurrences.word_rows(topic_id)}
    [generated] = [
        o for o in occurrences.by_source(topic_id) if o.candidate_id == word_ids["counter-offer"]
    ]
    _give_meaning(db_session, generated.id, generated.candidate_id)
    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)
    SqlaCandidateMeaningRepository(
        db_session, SessionChangeRecorder(db_session),
    ).delete_by_phrase_id(generated.id)
    db_session.commit()
    _add_source(db_session, "Reply", Kind.TEXT, ANOTHER_ARTICLE)
    db_session.commit()

    summary = _refresh_finding(db_session, container, topic_id, ANOTHER_ARTICLE, "Reply")

    assert summary.phrases_added == 1
    assert _texts(db_session, topic_id, "counter-offer") == [
        generated.source_phrase.text, LATER_ARTICLE, ANOTHER_ARTICLE,
    ]


def _collected(
    db_session: Session, container: Container, topic_id: int, lemma: str,
) -> NewCard:
    return next(
        c for c in container.refresh_topic_use_case(db_session)._collector.collect(topic_id)
        if c.word.lemma == lemma
    )


def _refresh_finding(
    db_session: Session, container: Container, topic_id: int, text_: str, title: str,
) -> TopicRefreshSummaryDTO:
    """Refresh as if the collector now found `text_` in `title` for counter-offer."""
    found = dataclasses.replace(
        _collected(db_session, container, topic_id, "counter-offer"),
        phrase=phrase(text_, "counter-offer"),
        origin=PhraseOrigin.from_source(title),
    )
    return _refresh_use_case(db_session, container, [found]).execute(topic_id)


def _refresh_use_case(
    db_session: Session, container: Container, collected: list[NewCard],
) -> RefreshTopicUseCase:
    collector = MagicMock()
    collector.collect.return_value = collected
    use_case = container.refresh_topic_use_case(db_session)
    return RefreshTopicUseCase(
        source_repo=SqlaSourceRepository(db_session, SessionChangeRecorder(db_session)),
        occurrence_repo=SqlaOccurrenceRepository(db_session, SessionChangeRecorder(db_session)),
        collected_phrases=CollectedPhrases(
            SqlaCandidateRepository(db_session, SessionChangeRecorder(db_session)),
            SqlaOccurrenceRepository(db_session, SessionChangeRecorder(db_session)),
            section_stamper(SqlaSettingsRepository(db_session, SessionChangeRecorder(db_session))),
        ),
        unit_of_work=use_case._unit_of_work,  # noqa: SLF001 — the container's own
        collector=collector,
        runner=use_case._runner,  # noqa: SLF001
    )


def test_a_second_refresh_adds_nothing(db_session: Session, container: Container) -> None:
    topic_id = _processed_topic(db_session, container)
    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)
    before = [o.id for o in SqlaOccurrenceRepository(
        db_session, SessionChangeRecorder(db_session),
    ).by_source(topic_id)]

    summary = container.refresh_topic_use_case(db_session).execute(topic_id)

    assert (summary.words_added, summary.phrases_added) == (0, 0)
    assert [o.id for o in SqlaOccurrenceRepository(
        db_session, SessionChangeRecorder(db_session),
    ).by_source(topic_id)] == before


def test_only_a_topic_is_refreshed(db_session: Session, container: Container) -> None:
    _processed_topic(db_session, container)

    with pytest.raises(RefreshNotSupportedError):
        container.refresh_topic_use_case(db_session).execute(
            _add_source(db_session, "Novel", Kind.TEXT, NOVEL_TEXT),
        )


def test_topic_cannot_be_processed_before_targets_exist(
    db_session: Session, container: Container,
) -> None:
    topic_id = _add_source(
        db_session, "Empty topic", None, "phrasal verbs with get",
        status=SourceStatus.NEW,
    )
    with pytest.raises(TopicTargetsMissingError):
        container.process_source_use_case(db_session).check(topic_id)


def test_refresh_does_not_restamp(db_session: Session, container: Container) -> None:
    topic_id = _processed_topic(db_session, container)
    db_session.execute(text("UPDATE phrases SET earned_section = 'extra'"))
    db_session.commit()
    stale = {o.id for o in SqlaOccurrenceRepository(
        db_session, SessionChangeRecorder(db_session),
    ).by_source(topic_id)}

    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)

    sections = {
        o.id: o.earned_section for o in SqlaOccurrenceRepository(
            db_session, SessionChangeRecorder(db_session),
        ).by_source(topic_id)
    }
    assert {sections[i] for i in stale} == {CandidateSection.EXTRA}

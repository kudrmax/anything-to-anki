"""A topic source collects real phrases from the other sources, offline.

Real spaCy, dictionaries and SQLite: targets are stored as if AI had already
generated them, then processing runs without AI. Topics are not rebuilt: a refresh
adds the phrases later sources give their targets, and changes nothing the topic has.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.topic_target import TopicTarget
from backend.domain.exceptions import (
    RebuildNotSupportedError,
    RefreshNotSupportedError,
    TopicTargetsMissingError,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.phrase_origin import PhraseOrigin
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)
from sqlalchemy import text

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

NOVEL_TEXT = "It was late. In the end we agreed to meet halfway on the price."
MEMOIR_FRAGMENT = "He refused to negotiate with them."
LATER_ARTICLE = "The company answered with a counter-offer the next morning."


def _add_source(
    session: Session,
    title: str,
    kind: Kind | None,
    text: str,
    status: SourceStatus = SourceStatus.DONE,
) -> int:
    """Content with a one-paragraph document, or a topic (no kind) asking for `text`."""
    source = SqlaSourceRepository(session).create(
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
    return source.id


def _add_memoir_with_candidate(session: Session) -> None:
    memoir_id = _add_source(
        session, "Memoir", Kind.TEXT, MEMOIR_FRAGMENT,
    )
    SqlaCandidateRepository(session).create_batch([
        StoredCandidate(
            source_id=memoir_id,
            lemma="negotiate",
            pos="VERB",
            cefr_level="B2",
            zipf_frequency=3.6,
            source_phrase=phrase(MEMOIR_FRAGMENT, "negotiate"),
            occurrences=1,
            status=CandidateStatus.PENDING,
        ),
    ])


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
    return topic_id


def _by_lemma(session: Session, source_id: int) -> dict[str, StoredCandidate]:
    return {c.lemma: c for c in SqlaCandidateRepository(session).get_by_source(source_id)}


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
    SqlaKnownWordRepository(db_session).add("salary", "NOUN")
    topic_id = _add_topic(db_session)

    use_case = container.process_source_use_case(db_session)
    use_case.start(topic_id)
    use_case.execute(topic_id)

    candidates = _by_lemma(db_session, topic_id)
    assert set(candidates) == {"negotiate", "meet halfway", "counter-offer"}

    negotiate = candidates["negotiate"]
    assert negotiate.source_phrase.text == MEMOIR_FRAGMENT
    assert negotiate.source_phrase.target_text() == "negotiate"
    assert negotiate.origin == PhraseOrigin.from_source("Memoir")

    meet_halfway = candidates["meet halfway"]
    assert meet_halfway.source_phrase.text == "In the end we agreed to meet halfway on the price."
    assert meet_halfway.source_phrase.target_text() == "meet halfway"
    assert meet_halfway.origin == PhraseOrigin.from_source("Novel")

    counter_offer = candidates["counter-offer"]
    assert counter_offer.source_phrase.text == LATER_ARTICLE
    assert counter_offer.source_phrase.target_text() == "counter-offer"
    assert counter_offer.origin == PhraseOrigin.from_source("Subtitles")

    topic = SqlaSourceRepository(db_session).get_by_id(topic_id)
    assert topic is not None
    assert topic.status == SourceStatus.DONE


def _processed_topic(db_session: Session, container: Container) -> int:
    topic_id = _add_topic(db_session)
    process = container.process_source_use_case(db_session)
    process.start(topic_id)
    db_session.commit()
    process.execute(topic_id)
    return topic_id


def _texts(db_session: Session, topic_id: int, lemma: str) -> list[str]:
    word_ids = {w.lemma: w.id for w in SqlaOccurrenceRepository(db_session).word_rows(topic_id)}
    return [
        o.source_phrase.text
        for o in SqlaOccurrenceRepository(db_session).by_source(topic_id)
        if o.candidate_id == word_ids[lemma]
    ]


def test_refreshing_picks_up_a_newly_added_source(
    db_session: Session, container: Container,
) -> None:
    topic_id = _processed_topic(db_session, container)
    assert _by_lemma(db_session, topic_id)["counter-offer"].origin == PhraseOrigin.generated()
    generated = _texts(db_session, topic_id, "counter-offer")

    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    summary = container.refresh_topic_use_case(db_session).execute(topic_id)

    assert (summary.words_added, summary.phrases_added) == (0, 1)
    assert _texts(db_session, topic_id, "counter-offer") == [*generated, LATER_ARTICLE]
    [added] = [
        o for o in SqlaOccurrenceRepository(db_session).by_source(topic_id)
        if o.source_phrase.text == LATER_ARTICLE
    ]
    assert added.origin is OccurrenceOrigin.COLLECTED
    assert added.shown_by is not None


def test_refreshing_keeps_decisions_and_results(
    db_session: Session, container: Container,
) -> None:
    topic_id = _processed_topic(db_session, container)
    occurrences = SqlaOccurrenceRepository(db_session)
    before = {o.id: o for o in occurrences.by_source(topic_id)}
    word_ids = {w.lemma: w.id for w in occurrences.word_rows(topic_id)}
    decided = next(o for o in before.values() if o.candidate_id == word_ids["counter-offer"])
    db_session.execute(
        text("UPDATE candidates SET status = 'learn' WHERE id = :id"),
        {"id": word_ids["counter-offer"]},
    )
    occurrences.set_decision(word_ids["counter-offer"], decided.id, None)
    SqlaCandidateMeaningRepository(db_session).upsert_for_phrase(decided.id, CandidateMeaning(
        candidate_id=decided.candidate_id, meaning="a reply offer", translation=None,
        synonyms=None, examples=None, ipa=None, generated_at=None,
    ))
    db_session.commit()
    before = {o.id: o for o in occurrences.by_source(topic_id)}

    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)

    after = {o.id: o for o in occurrences.by_source(topic_id)}
    assert {i: after[i] for i in before} == before
    [word] = [w for w in occurrences.word_rows(topic_id) if w.lemma == "counter-offer"]
    assert word.status is WordStatus.LEARN


def test_a_second_refresh_adds_nothing(db_session: Session, container: Container) -> None:
    topic_id = _processed_topic(db_session, container)
    _add_source(db_session, "Article", Kind.TEXT, LATER_ARTICLE)
    db_session.commit()
    container.refresh_topic_use_case(db_session).execute(topic_id)
    before = [o.id for o in SqlaOccurrenceRepository(db_session).by_source(topic_id)]

    summary = container.refresh_topic_use_case(db_session).execute(topic_id)

    assert (summary.words_added, summary.phrases_added) == (0, 0)
    assert [o.id for o in SqlaOccurrenceRepository(db_session).by_source(topic_id)] == before


def test_a_topic_is_refreshed_not_rebuilt(db_session: Session, container: Container) -> None:
    topic_id = _processed_topic(db_session, container)

    with pytest.raises(RebuildNotSupportedError):
        container.rebuild_source_use_case(db_session).execute(topic_id, include_open=False)
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
        container.process_source_use_case(db_session).start(topic_id)

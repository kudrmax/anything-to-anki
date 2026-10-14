"""A topic source collects real phrases from the other sources, offline.

Real spaCy, dictionaries and SQLite: targets are stored as if AI had already
generated them, then processing runs without AI. Topics are not rebuilt.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.topic_target import TopicTarget
from backend.domain.exceptions import RebuildNotSupportedError, TopicTargetsMissingError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.phrase_origin import PhraseOrigin
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)

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


def test_a_topic_is_not_rebuilt(db_session: Session, container: Container) -> None:
    topic_id = _add_topic(db_session)
    process = container.process_source_use_case(db_session)
    process.start(topic_id)
    process.execute(topic_id)

    with pytest.raises(RebuildNotSupportedError):
        container.rebuild_source_use_case(db_session).execute(topic_id, include_open=False)


def test_topic_cannot_be_processed_before_targets_exist(
    db_session: Session, container: Container,
) -> None:
    topic_id = _add_source(
        db_session, "Empty topic", None, "phrasal verbs with get",
        status=SourceStatus.NEW,
    )
    with pytest.raises(TopicTargetsMissingError):
        container.process_source_use_case(db_session).start(topic_id)

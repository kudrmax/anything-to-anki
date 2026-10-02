"""A topic source collects real phrases from the other sources, offline.

Real spaCy, dictionaries and SQLite: targets are stored as if AI had already
generated them, then processing (and reprocessing) runs without AI.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.entities.topic_target import TopicTarget
from backend.domain.exceptions import TopicTargetsMissingError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import resolve_content_type
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.phrase_origin import PhraseOrigin
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

NOVEL_TEXT = "It was late. In the end we agreed to meet halfway on the price."
MEMOIR_FRAGMENT = "He refused to negotiate with them."
LATER_ARTICLE = "The company answered with a counter-offer the next morning."


def _add_source(
    session: Session,
    title: str,
    input_method: InputMethod,
    raw_text: str,
    status: SourceStatus = SourceStatus.DONE,
    cleaned_text: str | None = None,
) -> int:
    source = SqlaSourceRepository(session).create(
        Source(
            raw_text=raw_text,
            title=title,
            status=status,
            input_method=input_method,
            content_type=resolve_content_type(input_method),
            cleaned_text=cleaned_text,
        ),
    )
    assert source.id is not None
    return source.id


def _add_memoir_with_candidate(session: Session) -> None:
    memoir_id = _add_source(
        session, "Memoir", InputMethod.TEXT_PASTED, MEMOIR_FRAGMENT,
        cleaned_text=MEMOIR_FRAGMENT,
    )
    SqlaCandidateRepository(session).create_batch([
        StoredCandidate(
            source_id=memoir_id,
            lemma="negotiate",
            pos="VERB",
            cefr_level="B2",
            zipf_frequency=3.6,
            context_fragment=MEMOIR_FRAGMENT,
            fragment_purity="clean",
            occurrences=1,
            surface_form="negotiate",
            status=CandidateStatus.PENDING,
        ),
    ])


def _add_topic(session: Session) -> int:
    topic_id = _add_source(
        session, "Salary talk", InputMethod.TOPIC_QUERY, "negotiating a salary",
        status=SourceStatus.NEW,
    )
    examples = [
        ("negotiate", "We had to **negotiate** a better deal."),
        ("meet halfway", "Let's **meet halfway** on this one."),
        ("counter-offer", "They sent a **counter-offer** at once."),
        ("salary", "My **salary** is paid every month."),
    ]
    SqlaTopicTargetRepository(session).create_batch([
        TopicTarget(source_id=topic_id, position=i, phrase=phrase, example=example)
        for i, (phrase, example) in enumerate(examples)
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
        db_session, "Novel", InputMethod.TEXT_PASTED, NOVEL_TEXT, status=SourceStatus.NEW,
    )
    _add_memoir_with_candidate(db_session)
    _add_source(
        db_session, "Raw subtitles", InputMethod.SUBTITLES_FILE,
        f"1\n00:00:01,000 --> 00:00:03,000\n{LATER_ARTICLE}\n", status=SourceStatus.NEW,
    )
    SqlaKnownWordRepository(db_session).add("salary", "NOUN")
    topic_id = _add_topic(db_session)

    use_case = container.process_source_use_case(db_session)
    use_case.start(topic_id)
    use_case.execute(topic_id)

    candidates = _by_lemma(db_session, topic_id)
    assert set(candidates) == {"negotiate", "meet halfway", "counter-offer"}

    negotiate = candidates["negotiate"]
    assert negotiate.context_fragment == MEMOIR_FRAGMENT
    assert negotiate.origin == PhraseOrigin.from_source("Memoir")

    meet_halfway = candidates["meet halfway"]
    assert meet_halfway.context_fragment == "In the end we agreed to meet halfway on the price."
    assert meet_halfway.origin == PhraseOrigin.from_source("Novel")

    counter_offer = candidates["counter-offer"]
    assert counter_offer.context_fragment == "They sent a counter-offer at once."
    assert counter_offer.origin == PhraseOrigin.generated()

    topic = SqlaSourceRepository(db_session).get_by_id(topic_id)
    assert topic is not None
    assert topic.status == SourceStatus.DONE
    assert topic.cleaned_text is not None
    assert set(topic.cleaned_text.split("\n")) == {
        c.context_fragment for c in candidates.values()
    }


def test_reprocessing_picks_up_a_newly_added_source(
    db_session: Session, container: Container,
) -> None:
    topic_id = _add_topic(db_session)
    process = container.process_source_use_case(db_session)
    process.start(topic_id)
    process.execute(topic_id)
    assert _by_lemma(db_session, topic_id)["counter-offer"].origin == PhraseOrigin.generated()

    _add_source(db_session, "Article", InputMethod.TEXT_PASTED, LATER_ARTICLE)
    container.reprocess_source_use_case(db_session).execute(topic_id)
    process.execute(topic_id)

    counter_offer = _by_lemma(db_session, topic_id)["counter-offer"]
    assert counter_offer.context_fragment == LATER_ARTICLE
    assert counter_offer.origin == PhraseOrigin.from_source("Article")


def test_topic_cannot_be_processed_before_targets_exist(
    db_session: Session, container: Container,
) -> None:
    topic_id = _add_source(
        db_session, "Empty topic", InputMethod.TOPIC_QUERY, "phrasal verbs with get",
        status=SourceStatus.NEW,
    )
    with pytest.raises(TopicTargetsMissingError):
        container.process_source_use_case(db_session).start(topic_id)

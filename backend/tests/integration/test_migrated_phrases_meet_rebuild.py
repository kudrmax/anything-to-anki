"""Phrases migration 0049 made from cards are found again by Rebuild at the same place.

The cards are what the real analysis cuts from the fixture text; after the migration, a
Rebuild preview of the unchanged text neither deletes them nor adds a phrase where they are,
with or without "Also unreviewed cards" — also where a phrase word is more than one token
of the analysis ("self-esteem").
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.application.dto.analysis_dtos import AnalyzeTextRequest
from backend.application.utils.source_rebuilder import SourceRebuilder
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.value_objects.document import (
    Document,
    Heading,
    Line,
    Paragraph,
    ParagraphMode,
)
from backend.infrastructure.api.dependencies import get_session_factory
from backend.infrastructure.container import Container
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.database import run_alembic_migrations
from backend.infrastructure.persistence.document_json import dump_document
from backend.infrastructure.persistence.models import PhraseModel, dump_phrase, dump_position
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from tests.candidate_sorter_support import section_stamper, threshold_resolver
from tests.media_files_support import WEIGHT_UNKNOWN, RemovedMediaFiles
from tests.migration_support import upgrade_to_head_with_sections
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from backend.application.dto.analysis_dtos import WordDTO
    from sqlalchemy.engine import Connection

pytestmark = pytest.mark.integration

SOURCE = 100  # migrations seed sources of their own
HYPHENATED = "esteem"
DOCUMENT = Document((
    Heading(level=1, text="A reluctant morning"),
    Paragraph(
        lines=(
            Line("The relentless pursuit of perfection often leads to burnout, and"),
            Line("she gave up her ambitions and wandered aimlessly through the meadow."),
        ),
        mode=ParagraphMode.FLOW,
    ),
    Paragraph(
        lines=(
            Line("He glared at the reluctant stranger with his fragile self-esteem."),
            Line("They lingered beside the dilapidated cottage until dusk."),
        ),
        mode=ParagraphMode.LINES,
    ),
))


@pytest.fixture(scope="module", autouse=True)
def _migrated_test_database() -> None:
    """The real analysis keeps its parses in the tests' database."""
    run_alembic_migrations(str(get_session_factory().kw["bind"].url))


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location", str(Path(database.__file__).parent.parent.parent / "alembic"),
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _analysis() -> list[WordDTO]:
    return Container().analyze_text_use_case().execute(
        DOCUMENT, AnalyzeTextRequest(user_level="B1"),
    ).words


def _seed_cards(conn: Connection, words: list[WordDTO]) -> None:
    """One card per word at its first occurrence, generated, as before the migration."""
    conn.execute(
        text(
            "INSERT INTO sources (id, title, status, role, created_at)"
            " VALUES (:id, 'title', 'done', 'content', '2026-01-01 00:00:00')"
        ),
        {"id": SOURCE},
    )
    conn.execute(
        text("INSERT INTO source_documents (source_id, document) VALUES (:id, :doc)"),
        {"id": SOURCE, "doc": dump_document(DOCUMENT)},
    )
    for card_id, word in enumerate(words, start=1):
        first = word.occurrences[0]
        conn.execute(
            text(
                "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency,"
                " is_sweet_spot, source_phrase, occurrences, status, is_phrasal_verb,"
                " phrase_position)"
                " VALUES (:id, :source, :lemma, :pos, :zipf, 0, :phrase, 1, 'pending',"
                " :phrasal, :position)"
            ),
            {
                "id": card_id, "source": SOURCE, "lemma": word.lemma, "pos": word.pos,
                "zipf": word.zipf_frequency, "phrasal": word.is_phrasal_verb,
                "phrase": dump_phrase(first.phrase),
                "position": dump_position(first.phrase_position.to_position()),
            },
        )
        conn.execute(
            text("INSERT INTO candidate_meanings (candidate_id, meaning) VALUES (:id, 'm')"),
            {"id": card_id},
        )


@pytest.fixture(scope="module")
def migrated(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, list[WordDTO]]:
    url = f"sqlite:///{tmp_path_factory.mktemp('migrated') / 'app.db'}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "0048")
    words = _analysis()
    with create_engine(url).begin() as conn:
        _seed_cards(conn, words)
    command.upgrade(cfg, "0049")
    upgrade_to_head_with_sections(cfg, url)
    return url, words


def _rebuilder(session: Session) -> SourceRebuilder:
    settings = SqlaSettingsRepository(session)
    vocabulary = user_vocabulary()
    sources = SqlaSourceRepository(session)
    occurrences = SqlaOccurrenceRepository(session)
    return SourceRebuilder(
        source_repo=sources,
        document_repo=SqlaDocumentRepository(session),
        occurrence_repo=occurrences,
        job_repo=SqlaJobRepository(session),
        media_repo=SqlaCandidateMediaRepository(session),
        media_files=RemovedMediaFiles(),
        settings_repo=settings,
        vocabulary=vocabulary,
        threshold_resolver=threshold_resolver(settings),
        stamper=section_stamper(settings),
        analyze_text_use_case=Container().analyze_text_use_case(),
        unit_of_work=SqlaUnitOfWork(session, vocabulary.scope),
        weight_unknown=WEIGHT_UNKNOWN,
    )


def _key(phrase: PhraseModel) -> OccurrenceKey:
    assert phrase.block is not None and phrase.line is not None and phrase.char is not None
    return OccurrenceKey(block=phrase.block, line=phrase.line, char=phrase.char)


@pytest.mark.parametrize("include_open", [False, True])
def test_a_rebuild_of_the_unchanged_text_keeps_every_migrated_phrase_in_place(
    migrated: tuple[str, list[WordDTO]], include_open: bool,
) -> None:
    url, words = migrated
    with Session(create_engine(url)) as session:
        phrases = list(session.scalars(select(PhraseModel)))
        rebuilder = _rebuilder(session)
        analysed = rebuilder.analyse(SOURCE)
        plan = rebuilder.plan(analysed, include_open)

    assert len(phrases) == len(words)
    assert HYPHENATED in {w.lemma for w in words}
    assert {p.origin for p in phrases} == {"auto"}
    word_keys = {
        row.id: row.key
        for row in SqlaOccurrenceRepository(Session(create_engine(url))).word_rows(SOURCE)
    }
    migrated_places = {(word_keys[p.candidate_id], _key(p)) for p in phrases}
    inserted_places = {(i.word, i.occurrence.key) for i in plan.occ_to_insert}
    analysed_places = {(w.key, o.key) for w in analysed.words for o in w.occurrences}
    assert migrated_places <= analysed_places
    assert plan.occ_to_delete == ()
    assert plan.words_to_delete == ()
    assert plan.words_to_create == ()
    assert migrated_places.isdisjoint(inserted_places)
    assert plan.occ_to_update_text == ()
    assert plan.occ_to_rekey == ()

"""Migration 0048 adds unknown words and carries a card's old phrase columns into card phrases."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from alembic import command
from alembic.config import Config
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.infrastructure.persistence import database
from backend.infrastructure.persistence.models import load_phrase
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.engine import Connection

pytestmark = pytest.mark.integration

REVISION_BEFORE = "0047"
REVISION_UNDER_TEST = "0048"
SOURCE_ID = 100
OLD_COLUMNS = {
    "fragment_unknown_count", "fragment_purity", "context_fragment", "surface_form",
    "has_custom_context_fragment", "polished_fragment", "target_position",
}

TWO_BANKS = "The bank stands by the river bank."
SEPARATED = "Well — she gave it up."
RAN = "He ran home quickly."
DOGS = "The dogs bark at night."
BENCH_LINES = ("I just witnessed", "this guy bench-pressing the moon.")
CATCHING_UP = "We are catching up on the news."
BROUGHT_UP = "She brought it up again."
DONG = "The dong sounded twice."


def _alembic_config(db_url: str) -> Config:
    cfg = Config()
    alembic_dir = Path(database.__file__).parent.parent.parent / "alembic"
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _whole_line(block: int, line: str) -> str:
    return json.dumps([block, 0, 0, 0, len(line)])


def _span(block: int, start: int, end: int, line: int = 0) -> str:
    return json.dumps([block, line, start, line, end])


def _first_to_last(block: int, line: str, first: str, last: str) -> str:
    """The old target position: from the target's first word to its last."""
    return _span(block, line.index(first), line.rindex(last) + len(last))


def _add_candidate(
    conn: Connection,
    candidate_id: int,
    lemma: str,
    fragment: str,
    *,
    surface_form: str | None = None,
    polished: str | None = None,
    phrase_position: str | None = None,
    target_position: str | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " context_fragment, fragment_purity, fragment_unknown_count, occurrences, status,"
            " surface_form, is_phrasal_verb, has_custom_context_fragment, polished_fragment,"
            " phrase_position, target_position)"
            " VALUES (:id, :source, :lemma, 'NOUN', 3.9, 1, :fragment, 'clean', 0, 1,"
            " 'pending', :surface, 0, 0, :polished, :phrase_position, :target_position)",
        ),
        {
            "id": candidate_id, "source": SOURCE_ID, "lemma": lemma, "fragment": fragment,
            "surface": surface_form, "polished": polished,
            "phrase_position": phrase_position, "target_position": target_position,
        },
    )


def _seed_old_cards(db_url: str) -> None:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO sources (id, title, status, role, created_at)"
            f" VALUES ({SOURCE_ID}, 'title', 'done', 'content', '2026-01-01 00:00:00')",
        ))
        SqlaDocumentRepository(Session(bind=conn)).save(SOURCE_ID, Document((
            *(
                Paragraph(lines=(Line(line),), mode=ParagraphMode.FLOW)
                for line in (TWO_BANKS, SEPARATED)
            ),
            Paragraph(lines=tuple(Line(line) for line in BENCH_LINES), mode=ParagraphMode.FLOW),
            *(
                Paragraph(lines=(Line(line),), mode=ParagraphMode.FLOW)
                for line in (CATCHING_UP, BROUGHT_UP)
            ),
        )))
        second_bank = TWO_BANKS.rindex("bank")
        _add_candidate(
            conn, 1, "bank", TWO_BANKS, surface_form="bank",
            phrase_position=_whole_line(0, TWO_BANKS),
            target_position=_span(0, second_bank, second_bank + len("bank")),
        )
        _add_candidate(
            conn, 2, "give up", SEPARATED, surface_form="gave it up", polished=SEPARATED,
            phrase_position=_whole_line(1, SEPARATED),
            target_position=_first_to_last(1, SEPARATED, "gave", "up"),
        )
        _add_candidate(conn, 3, "run", RAN, surface_form="ran", polished="He ran home.")
        _add_candidate(conn, 4, "dog", DOGS, polished="They make noise at night.")
        # The old phrase kept the line break the document joins with a space; the lemma
        # is not found in the text, so only the document can place the target.
        bench = BENCH_LINES[1].index("bench")
        _add_candidate(
            conn, 5, "bench-press", "\n".join(BENCH_LINES),
            phrase_position=json.dumps([2, 0, 0, 1, len(BENCH_LINES[1])]),
            target_position=_span(2, bench, bench + len("bench"), line=1),
        )
        _add_candidate(
            conn, 6, "catch up on", CATCHING_UP,
            phrase_position=_whole_line(3, CATCHING_UP),
            target_position=_first_to_last(3, CATCHING_UP, "catching", "on"),
        )
        _add_candidate(
            conn, 7, "bring up", BROUGHT_UP,
            phrase_position=_whole_line(4, BROUGHT_UP),
            target_position=_first_to_last(4, BROUGHT_UP, "brought", "up"),
        )
        _add_candidate(conn, 8, "dong", DONG, polished="The bell rang with a ding-dong.")
        # Old cloze numbers count words by spaces: "Well", "—", "she", "gave", "it", "up."
        conn.execute(text(
            "INSERT INTO candidate_clozes (candidate_id, hidden_word_indices, hint_kind, phrase)"
            " VALUES (2, '[3, 5]', 'none', :phrase)",
        ), {"phrase": SEPARATED})


def _upgraded(tmp_path: Path) -> str:
    db_url = f"sqlite:///{tmp_path / 'app.db'}"
    cfg = _alembic_config(db_url)
    command.upgrade(cfg, REVISION_BEFORE)
    _seed_old_cards(db_url)
    command.upgrade(cfg, REVISION_UNDER_TEST)
    return db_url


def _phrases(db_url: str) -> dict[int, tuple[Phrase, Phrase | None]]:
    with create_engine(db_url).connect() as conn:
        rows = conn.execute(text("SELECT id, source_phrase, polished_phrase FROM candidates"))
        result: dict[int, tuple[Phrase, Phrase | None]] = {}
        for candidate_id, source, polished in rows:
            loaded = load_phrase(source)
            assert loaded is not None
            result[candidate_id] = (loaded, load_phrase(polished))
        return result


@pytest.fixture(scope="module")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    return _upgraded(tmp_path_factory.mktemp("migration_0048"))


def test_schema_has_unknown_words_and_card_phrases(db_url: str) -> None:
    inspector = inspect(create_engine(db_url))
    columns = {c["name"] for c in inspector.get_columns("candidates")}
    assert "unknown_words" in inspector.get_table_names()
    assert {"source_phrase", "polished_phrase"} <= columns
    assert not columns & OLD_COLUMNS


def test_target_is_taken_from_its_old_position_in_the_document(db_url: str) -> None:
    source, _ = _phrases(db_url)[1]
    assert source.text == TWO_BANKS
    assert source.target == (len(source.words) - 1,)


def test_separated_phrasal_verb_targets_its_verb_and_particle(db_url: str) -> None:
    source, _ = _phrases(db_url)[2]
    assert source.target_text() == "gave up"
    assert [source.word_text(i) for i in source.target] == ["gave", "up"]


def test_multi_line_phrase_takes_its_target_from_the_document(db_url: str) -> None:
    source, _ = _phrases(db_url)[5]
    assert source.text == "\n".join(BENCH_LINES)
    assert source.target_text() == "bench-pressing"


def test_three_word_phrasal_verb_targets_all_its_words(db_url: str) -> None:
    source, _ = _phrases(db_url)[6]
    assert [source.word_text(i) for i in source.target] == ["catching", "up", "on"]


def test_object_between_verb_and_particle_stays_outside_the_target(db_url: str) -> None:
    source, _ = _phrases(db_url)[7]
    assert [source.word_text(i) for i in source.target] == ["brought", "up"]


def test_without_a_position_the_target_is_found_by_surface_form(db_url: str) -> None:
    source, _ = _phrases(db_url)[3]
    assert source.text == RAN
    assert source.target_text() == "ran"


def test_without_a_position_or_surface_form_the_target_is_found_by_lemma(db_url: str) -> None:
    source, _ = _phrases(db_url)[4]
    assert source.target_text() == "dogs"


def test_polished_text_equal_to_the_source_reuses_the_source_phrase(db_url: str) -> None:
    source, polished = _phrases(db_url)[2]
    assert polished == source


def test_polished_text_with_the_target_becomes_a_phrase(db_url: str) -> None:
    _, polished = _phrases(db_url)[3]
    assert polished is not None
    assert polished.text == "He ran home."
    assert polished.target_text() == "ran"


def test_polished_text_with_the_target_inside_a_hyphenated_word_is_kept(db_url: str) -> None:
    _, polished = _phrases(db_url)[8]
    assert polished is not None
    assert polished.target_text() == "ding-dong"


def test_polished_text_without_the_target_is_dropped(db_url: str) -> None:
    _, polished = _phrases(db_url)[4]
    assert polished is None


def test_cloze_hidden_words_are_renumbered_by_the_new_words(db_url: str) -> None:
    with create_engine(db_url).connect() as conn:
        hidden = conn.execute(text(
            "SELECT hidden_word_indices FROM candidate_clozes WHERE candidate_id = 2",
        )).scalar_one()
    source, _ = _phrases(db_url)[2]
    indices = json.loads(hidden)
    assert [source.word_text(i) for i in indices] == ["gave", "up"]
    assert indices == [2, 4]

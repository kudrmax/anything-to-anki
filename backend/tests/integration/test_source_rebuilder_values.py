"""A level change analyses every source with the values it is about to save, and applies all
of them inside its one write."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.utils.source_rebuilder import AnalysisValues
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork

from tests.source_rebuild_support import SOURCE, Bench, at, word

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SAVED_LEVEL = "B1"
NEW_LEVEL = "C1"
NEW_ZIPF = 4.2


def _write(bench: Bench) -> AbstractContextManager[None]:
    return SqlaUnitOfWork(bench.session, bench.vocabulary.scope).write()


def test_analyse_uses_given_values_not_saved_ones(db_session: Session) -> None:
    bench = Bench(db_session)
    bench.processed(word("ledge", at(0)))

    values = AnalysisValues(user_level=NEW_LEVEL, frequent_word_zipf=NEW_ZIPF)
    bench.rebuilder().analyse(SOURCE, values)

    request = bench.analyze_text.execute.call_args.args[1]
    assert (request.user_level, request.frequent_word_zipf) == (NEW_LEVEL, NEW_ZIPF)


def test_analyse_without_values_reads_settings(db_session: Session) -> None:
    bench = Bench(db_session)
    bench.processed(word("ledge", at(0)))

    bench.rebuilder().analyse(SOURCE)

    assert bench.analyze_text.execute.call_args.args[1].user_level == SAVED_LEVEL


def test_apply_inside_writes_only_with_the_callers_write(db_session: Session) -> None:
    bench = Bench(db_session)
    bench.processed(word("ledge", at(0)))
    bench.analysis = [word("ledge", at(0)), word("parapet", at(1))]
    rebuilder = bench.rebuilder()
    analysed = rebuilder.analyse(SOURCE)

    with _write(bench):
        applied = rebuilder.apply_inside(analysed, RebuildMode.UPDATE)

    assert len(bench.phrases()) == 2
    assert len(applied.plan.occ_to_insert) == 1
    assert bench.media_files.removed == []


def test_apply_inside_rolls_back_with_the_callers_write(db_session: Session) -> None:
    bench = Bench(db_session)
    bench.processed(word("ledge", at(0)))
    bench.analysis = [word("ledge", at(0)), word("parapet", at(1))]
    rebuilder = bench.rebuilder()
    analysed = rebuilder.analyse(SOURCE)

    with pytest.raises(RuntimeError), _write(bench):
        rebuilder.apply_inside(analysed, RebuildMode.UPDATE)
        raise RuntimeError

    assert len(bench.phrases()) == 1

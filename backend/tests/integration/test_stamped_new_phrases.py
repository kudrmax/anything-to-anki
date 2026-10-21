"""A new phrase is stored with the section it earns; one stored without it fails to read."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import PhraseSectionMissingError
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.rebuild_mode import RebuildMode
from sqlalchemy import text

from tests.source_rebuild_support import SOURCE, Bench, at, word

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


def test_processing_stamps_every_inserted_phrase(bench: Bench) -> None:
    bench.processed(
        word("zephyr", at(1, text="a zephyr quill", new=("quill",))),
        word("glare", at(0)),
    )

    assert bench.phrase_on("zephyr", 1).earned_section == CandidateSection.EXTRA.value
    assert bench.phrase_on("glare", 0).earned_section == CandidateSection.READY.value


def test_rebuild_stamps_the_phrases_it_adds(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    bench.analysis = [
        word("glare", at(0)),
        word("zephyr", at(1, text="a zephyr quill", new=("quill",))),
    ]

    bench.rebuild().execute(SOURCE, RebuildMode.UPDATE)

    assert bench.phrase_on("zephyr", 1).earned_section == CandidateSection.EXTRA.value


def test_reading_a_phrase_without_a_section_is_refused(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    stored = bench.phrase_on("glare", 0)
    bench.session.execute(text("UPDATE phrases SET earned_section = NULL"))
    bench.session.commit()

    with pytest.raises(PhraseSectionMissingError, match="has no section"):
        bench.occurrences.get(stored.id)

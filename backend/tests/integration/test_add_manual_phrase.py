"""A word added by selecting it in the source: a phrase of its word, kept by Rebuild."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.analysis_dtos import OccurrenceDTO, OccurrenceKeyDTO
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.use_cases.add_manual_candidate import AddManualCandidateUseCase
from backend.application.utils.export_queue import ExportQueue
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import ActionRefusedError
from backend.domain.services.card_view import Command, Where
from backend.domain.services.rebuild_plan import SectionChange
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice, Press
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork

from tests.candidate_sorter_support import section_stamper
from tests.decision_support import Decisions
from tests.lock_support import free_lock
from tests.phrase_support import phrase
from tests.source_rebuild_support import LINES, SOURCE, Bench, at, word

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

LINGER_LINE = 3  # "We lingered a while."
LINGER_CHAR = LINES[LINGER_LINE].index("lingered")
GLARE_LINE = 1  # "She glared back."
GLARE_CHAR = LINES[GLARE_LINE].index("glared")
LEMMAS = {"lingered": "linger", "glared": "glare"}


def _token(text: str) -> TokenData:
    return TokenData(
        index=0, text=text, lemma=LEMMAS.get(text.lower(), text.lower()), pos="VERB",
        tag="VBD", head_index=0, children_indices=(), is_punct=False, is_stop=False,
        is_alpha=True, is_propn=False, sent_index=0,
    )


def _read_picked(text: str, picked: list[int]) -> Phrase:
    return phrase(text).with_target(tuple(picked))


class Manual:
    """Adding words to the bench's source by selecting whole lines."""

    def __init__(self, bench: Bench) -> None:
        self.bench = bench
        analyzer = MagicMock()
        analyzer.analyze.side_effect = lambda text: [_token(w.strip(".,")) for w in text.split()]
        detector = MagicMock()
        detector.detect.return_value = []
        classifier = MagicMock()
        classifier.classify_detailed.return_value = CEFRBreakdown(
            final_level=CEFRLevel.C1, decision_method="voting", priority_votes=[], votes=[],
        )
        frequency = MagicMock()
        frequency.get_zipf_value.return_value = 3.0
        reader = MagicMock()
        reader.read_picked.side_effect = _read_picked
        decisions = Decisions(bench.session)
        self.use_case = AddManualCandidateUseCase(
            source_repo=bench.sources,
            document_repo=SqlaDocumentRepository(bench.session),
            candidate_repo=bench.candidates,
            occurrence_repo=bench.occurrences,
            text_analyzer=analyzer,
            cefr_classifier=classifier,
            frequency_provider=frequency,
            phrasal_verb_detector=detector,
            phrase_reader=reader,
            stamper=section_stamper(SqlaSettingsRepository(bench.session)),
            lock=free_lock(),
            card_views=MagicMock(),
            decide_phrase=decisions.decide_phrase(),
            unit_of_work=SqlaUnitOfWork(bench.session, decisions.scope),
        )

    def add(self, line: int, word_index: int) -> None:
        self.use_case.execute(SOURCE, [word_index], SelectionDTO(
            start_block=0, start_line=line, start_char=0,
            end_block=0, end_line=line, end_char=len(LINES[line]),
        ))
        self.bench.session.commit()

@pytest.fixture
def bench(db_session: Session) -> Bench:
    return Bench(db_session)


def _of(bench: Bench, lemma: str) -> list[Occurrence]:
    [found] = [w for w in bench.occurrences.word_rows(SOURCE) if w.lemma == lemma]
    return bench.occurrences.of_word(found.id)


def _shown(bench: Bench, lemma: str) -> list[Occurrence]:
    return [o for o in _of(bench, lemma) if o.is_shown]


def _at(line: int, char: int) -> OccurrenceDTO:
    shown = LINES[line]
    return OccurrenceDTO(
        phrase=phrase(shown),
        phrase_position=DocumentPositionDTO(
            block=0, start_line=line, start_char=0, end_line=line, end_char=len(shown),
        ),
        key=OccurrenceKeyDTO(block=0, line=line, char=char),
        fragment_score=0.5,
    )


# ── a new word ────────────────────────────────────────────────────────


def test_a_new_word_gets_a_manual_phrase_with_its_key(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    Manual(bench).add(LINGER_LINE, 1)

    [added] = _of(bench, "linger")
    assert added.origin is OccurrenceOrigin.MANUAL
    assert added.shown_by is ShownBy.USER
    assert added.key == OccurrenceKey(block=0, line=LINGER_LINE, char=LINGER_CHAR)
    assert added.source_phrase.text == LINES[LINGER_LINE]


def test_a_manual_phrase_then_rebuild_keeps_one_card_at_its_place(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    Manual(bench).add(LINGER_LINE, 1)
    bench.analysis = [word("glare", at(0)), word("linger", _at(LINGER_LINE, LINGER_CHAR))]

    bench.rebuild().execute(SOURCE, include_open=True)

    assert [o.key for o in _shown(bench, "linger")] == [
        OccurrenceKey(block=0, line=LINGER_LINE, char=LINGER_CHAR),
    ]
    assert len(_of(bench, "linger")) == 1


# ── a word the source has ─────────────────────────────────────────────


def test_an_existing_word_gets_a_second_shown_phrase(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    Manual(bench).add(GLARE_LINE, 1)

    assert len(bench.occurrences.word_rows(SOURCE)) == 1
    shown = _shown(bench, "glare")
    assert [(o.origin, o.shown_by) for o in shown] == [
        (OccurrenceOrigin.AUTO, ShownBy.SELECTION), (OccurrenceOrigin.MANUAL, ShownBy.USER),
    ]
    assert shown[1].key == OccurrenceKey(block=0, line=GLARE_LINE, char=GLARE_CHAR)


def test_a_manual_add_at_a_hidden_auto_phrase_shows_it_without_a_duplicate(
    bench: Bench,
) -> None:
    bench.processed(word("glare", at(0, 0.1), _at(GLARE_LINE, GLARE_CHAR)))
    hidden = bench.phrase_on("glare", GLARE_LINE)
    assert hidden.shown_by is None
    bench.set_choice(hidden.id, "skip")

    Manual(bench).add(GLARE_LINE, 1)

    occurrences = _of(bench, "glare")
    assert len(occurrences) == 2
    made_shown = next(o for o in occurrences if o.id == hidden.id)
    assert made_shown.shown_by is ShownBy.USER
    assert made_shown.choice is not CardChoice.SKIP
    assert not made_shown.replaces_selection

    bench.rebuild().execute(SOURCE, include_open=True)

    assert sorted(o.id for o in _shown(bench, "glare")) == sorted(o.id for o in occurrences)


def test_showing_a_hidden_phrase_restamps_the_section_it_earns_now(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 0.1), _at(GLARE_LINE, GLARE_CHAR)))
    [hidden] = [o for o in _of(bench, "glare") if o.shown_by is None]
    stale = CandidateSection.PROBABLY_KNOWN
    bench.occurrences.set_earned_sections([SectionChange(hidden.id, stale)])
    bench.session.commit()

    Manual(bench).add(GLARE_LINE, 1)

    [shown] = [o for o in _of(bench, "glare") if o.id == hidden.id]
    assert shown.shown_by is ShownBy.USER
    assert shown.earned_section is not stale


@pytest.mark.parametrize("decided", ["on_another_card", "in_the_known_list"])
def test_a_skipped_phrase_of_a_decided_word_is_shown_and_stays_done(
    bench: Bench, decided: str,
) -> None:
    bench.processed(word("glare", at(0, 0.1), _at(GLARE_LINE, GLARE_CHAR)))
    hidden = bench.phrase_on("glare", GLARE_LINE)
    bench.set_choice(hidden.id, "skip")
    if decided == "on_another_card":
        bench.decide_learn("glare", bench.phrase_on("glare", 0).id)
    else:
        SqlaKnownWordRepository(bench.session).add("glare", None)
        bench.session.commit()

    Manual(bench).add(GLARE_LINE, 1)

    made_shown = next(o for o in _of(bench, "glare") if o.id == hidden.id)
    assert (made_shown.shown_by, made_shown.choice) == (ShownBy.USER, CardChoice.SKIP)


def test_a_manual_add_on_the_selection_card_keeps_one_card(bench: Bench) -> None:
    bench.processed(word("glare", _at(GLARE_LINE, GLARE_CHAR), at(4, 0.9)))
    card = bench.phrase_on("glare", GLARE_LINE)
    assert card.shown_by == ShownBy.SELECTION.value

    Manual(bench).add(GLARE_LINE, 1)
    bench.rebuild().execute(SOURCE, include_open=True)

    shown = _shown(bench, "glare")
    assert [(o.id, o.shown_by) for o in shown] == [(card.id, ShownBy.USER)]
    assert shown[0].replaces_selection


def test_adding_the_same_selection_twice_shows_one_manual_card(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    manual = Manual(bench)
    manual.add(GLARE_LINE, 1)
    [added] = [o for o in _of(bench, "glare") if o.origin is OccurrenceOrigin.MANUAL]
    assert added.id is not None
    bench.set_choice(added.id, "skip")

    manual.add(GLARE_LINE, 1)

    manuals = [o for o in _of(bench, "glare") if o.origin is OccurrenceOrigin.MANUAL]
    assert [(o.id, o.shown_by, o.choice) for o in manuals] == [
        (added.id, ShownBy.USER, CardChoice.NONE),
    ]


def test_a_manual_add_keeps_the_decision_card(bench: Bench) -> None:
    bench.processed(word("glare", at(0, 0.1), _at(GLARE_LINE, GLARE_CHAR)))
    decision = bench.phrase_on("glare", 0)
    bench.decide_learn("glare", decision.id)

    Manual(bench).add(GLARE_LINE, 1)
    bench.rebuild().execute(SOURCE, include_open=True)

    shown = _shown(bench, "glare")
    assert [o.id for o in shown if o.card_state.is_decision] == [decision.id]
    assert len(shown) == 2


def test_learn_on_a_manual_card_closes_the_word_and_exports_one_phrase(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))
    Manual(bench).add(GLARE_LINE, 1)
    first, manual = _shown(bench, "glare")
    assert manual.id is not None
    decisions = Decisions(bench.session)
    decide = decisions.decide_phrase()

    decide.press(manual.id, Press.LEARN)

    assert first.id is not None
    sibling = decide.view(first.id)
    assert sibling.shown.where is Where.OTHER_CARD
    assert sibling.shown.status is WordStatus.LEARN
    assert {b.command for b in sibling.buttons} == {None}
    decision_card = decide.view(manual.id)
    learn = next(b for b in decision_card.buttons if b.button is Press.LEARN)
    assert learn.pressed
    assert learn.command is Command.DECIDE
    with pytest.raises(ActionRefusedError):
        decide.press(first.id, Press.KNOWN)
    queue = ExportQueue(
        bench.candidates, bench.occurrences, decisions.word_states, decisions.vocabulary,
    )
    [card] = queue.for_source(SOURCE).pending
    assert card.phrase.id == manual.id


def test_a_manual_phrase_is_stamped(bench: Bench) -> None:
    bench.processed(word("glare", at(0)))

    Manual(bench).add(LINGER_LINE, 1)

    [added] = _of(bench, "linger")
    assert added.earned_section is CandidateSection.READY

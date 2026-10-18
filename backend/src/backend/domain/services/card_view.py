"""What a card shows, derived from the decision tables and `status_of` (design §2.9)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.domain.services.decision_rules import PRESS_RULES, press_key, role_of, rule
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import (
    CardChoice,
    CardState,
    DecisionStatus,
    Press,
    Refusal,
    Role,
    WordState,
    decision_reads_known,
    decision_status,
    in_anki,
    reads_known,
    status_of,
)
from backend.domain.value_objects.card_note import CardNote
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge


class Command(StrEnum):
    DECIDE = "decide"
    EDIT_CLOZE = "edit_cloze"   # the editor opens; its Save is the press


class Where(StrEnum):
    HERE = "here"
    OTHER_CARD = "other_card"
    OTHER_SOURCE = "other_source"
    NOWHERE = "nowhere"


@dataclass(frozen=True)
class ButtonState:
    button: Press
    command: Command | None
    pressed: bool
    refused: Refusal | None


@dataclass(frozen=True)
class Shown:
    status: WordStatus
    skipped: bool
    where: Where


@dataclass(frozen=True)
class CardView:
    card_id: int
    buttons: tuple[ButtonState, ...]
    can_edit_cloze: bool
    note: CardNote | None
    known_on: datetime | None     # when a card in Anki reads Known by its timer
    shown: Shown
    is_protected: bool
    wants_generation: bool

    @property
    def is_done(self) -> bool:
        return self.shown.status is not WordStatus.NEW or self.shown.skipped


# --- buttons ----------------------------------------------------------------------------

_COMMANDS: Mapping[tuple[bool, bool], Command | None] = MappingProxyType(
    {  # (refused, opens the cloze editor)
        (True, False): None,
        (False, True): Command.EDIT_CLOZE,
        (False, False): Command.DECIDE,
    },
)
_SHOWN_PRESS: Mapping[tuple[CardChoice, bool], Press | None] = MappingProxyType(
    {  # (the decision card's choice, it reads Known)
        (CardChoice.NONE, False): None,
        (CardChoice.LEARN, False): Press.LEARN,
        (CardChoice.CLOZE, False): Press.CLOZE,
        (CardChoice.KNOWN, False): Press.KNOWN,
        (CardChoice.LEARN, True): Press.KNOWN,
        (CardChoice.CLOZE, True): Press.KNOWN,
    },
)


def _button(
    word: WordState, card: CardState, button: Press, shown_press: Press | None,
    lemma: LemmaKnowledge, elsewhere: ElsewhereStatus | None, now: datetime,
) -> ButtonState:
    target = rule(PRESS_RULES, press_key(word, card.card_id, button, lemma, elsewhere, now))
    opens_editor = button is Press.CLOZE and target.choice is CardChoice.CLOZE
    return ButtonState(
        button=button,
        command=_COMMANDS[(target.refusal is not None, opens_editor)],
        pressed=button is shown_press or (button is Press.SKIP and card.choice is CardChoice.SKIP),
        refused=target.refusal,
    )


# --- note -------------------------------------------------------------------------------


@dataclass(frozen=True)
class NoteKey:
    role: Role
    bound: bool
    known_choice: bool
    reads_known: bool
    listed: bool                        # normalised: reads Known through the Known list
    elsewhere: ElsewhereStatus | None   # normalised: OPEN cards only
    unknown: bool = False               # normalised: a Learning card in Anki, lemma in Unknown


@dataclass(frozen=True)
class NoteRow:
    note: CardNote | None
    dated: bool = False


def possible_note(key: NoteKey) -> bool:
    decision = key.role is Role.DECISION
    return (
        (key.elsewhere is None or key.role is Role.OPEN)
        and (not key.bound or decision)
        and (not key.known_choice or decision)
        and (not key.reads_known or (decision and not key.known_choice))
        and (not key.reads_known or key.bound or key.listed)
        and (not key.listed or key.reads_known)
        and (not key.unknown or (key.bound and not key.known_choice and not key.reads_known))
    )


_ELSEWHERE_NOTES: Mapping[ElsewhereStatus | None, CardNote | None] = MappingProxyType(
    {
        None: None,
        ElsewhereStatus.KNOWN: CardNote.KNOWN_ELSEWHERE,
        ElsewhereStatus.LEARNING: CardNote.LEARNING_ELSEWHERE,
        ElsewhereStatus.LEARN: CardNote.LEARN_ELSEWHERE,
    },
)
NOTE_RULES: Mapping[NoteKey, NoteRow] = MappingProxyType(
    {
        **{
            NoteKey(Role.OPEN, False, False, False, False, elsewhere): NoteRow(note)
            for elsewhere, note in _ELSEWHERE_NOTES.items()
        },
        NoteKey(Role.OTHER, False, False, False, False, None):
            NoteRow(CardNote.DECIDED_ON_OTHER_CARD),
        NoteKey(Role.DECISION, False, False, False, False, None): NoteRow(None),
        NoteKey(Role.DECISION, False, True, False, False, None): NoteRow(None),
        NoteKey(Role.DECISION, True, False, False, False, None):
            NoteRow(CardNote.IN_ANKI, dated=True),
        NoteKey(Role.DECISION, True, True, False, False, None): NoteRow(CardNote.IN_ANKI),
        NoteKey(Role.DECISION, True, False, True, False, None):
            NoteRow(CardNote.KNOWN_BY_TIMER, dated=True),
        NoteKey(Role.DECISION, True, False, True, True, None): NoteRow(CardNote.KNOWN_BY_LIST),
        # Q15: a Learn not in Anki yet whose lemma was put in Known after it.
        NoteKey(Role.DECISION, False, False, True, True, None): NoteRow(CardNote.KNOWN_BY_LIST),
        # Unknown wins (Q8): the timer never makes it Known, so there is no date.
        NoteKey(Role.DECISION, True, False, False, False, None, unknown=True):
            NoteRow(CardNote.IN_ANKI),
    },
)


def _open_elsewhere(role: Role, elsewhere: ElsewhereStatus | None) -> ElsewhereStatus | None:
    return elsewhere if role is Role.OPEN else None


def note_key(
    word: WordState, card: CardState, lemma: LemmaKnowledge, elsewhere: ElsewhereStatus | None,
    now: datetime,
) -> NoteKey:
    role = role_of(word, card)
    known = reads_known(card, lemma, now)
    return NoteKey(
        role=role,
        bound=in_anki(card),
        known_choice=card.choice is CardChoice.KNOWN,
        reads_known=known,
        listed=known and lemma.known_marked,
        elsewhere=_open_elsewhere(role, elsewhere),
        unknown=in_anki(card) and card.choice is not CardChoice.KNOWN and lemma.unknown,
    )


def _known_on(card: CardState, row: NoteRow) -> datetime | None:
    binding = card.binding
    return binding.learning_since + LEARNING_KNOWN_AFTER if row.dated and binding else None


# --- shown ------------------------------------------------------------------------------

_WHERE: Mapping[tuple[Role, bool], Where] = MappingProxyType(
    {  # (role, decided in another source)
        (Role.DECISION, False): Where.HERE,
        (Role.OTHER, False): Where.OTHER_CARD,
        (Role.OPEN, True): Where.OTHER_SOURCE,
        (Role.OPEN, False): Where.NOWHERE,
    },
)
_SEEN_ELSEWHERE: Mapping[ElsewhereStatus | None, WordStatus] = MappingProxyType(
    {
        ElsewhereStatus.KNOWN: WordStatus.KNOWN,
        ElsewhereStatus.LEARNING: WordStatus.LEARNING,
        ElsewhereStatus.LEARN: WordStatus.LEARN,
    },
)


def _shown(
    word: WordState, card: CardState, open_elsewhere: ElsewhereStatus | None,
    lemma: LemmaKnowledge, now: datetime,
) -> Shown:
    """An open word's own status is NEW, so the other source's status shows instead."""
    return Shown(
        status=_SEEN_ELSEWHERE.get(open_elsewhere, status_of(word, lemma, now)),
        skipped=card.choice is CardChoice.SKIP,
        where=_WHERE[(role_of(word, card), open_elsewhere is not None)],
    )


# --- the view ---------------------------------------------------------------------------


def card_view(
    word: WordState, card_id: int, lemma: LemmaKnowledge, elsewhere: ElsewhereStatus | None,
    now: datetime,
) -> CardView:
    card = word.card(card_id)
    role = role_of(word, card)
    open_elsewhere = _open_elsewhere(role, elsewhere)
    shown_press = _SHOWN_PRESS[(word.decision_choice, decision_reads_known(word, lemma, now))]
    note = NOTE_RULES[note_key(word, card, lemma, elsewhere, now)]
    return CardView(
        card_id=card_id,
        buttons=tuple(
            _button(word, card, button, shown_press, lemma, elsewhere, now) for button in Press
        ),
        can_edit_cloze=card.choice is CardChoice.CLOZE and not in_anki(card),
        note=note.note,
        known_on=_known_on(card, note),
        shown=_shown(word, card, open_elsewhere, lemma, now),
        is_protected=is_protected(card),
        wants_generation=(
            (role is Role.DECISION and in_export_queue(word, lemma, now))
            or (role is Role.OPEN and card.choice is CardChoice.NONE and open_elsewhere is None)
        ),
    )


def is_protected(card: CardState) -> bool:
    """The choice or the binding; rebuild adds its user-work rule on top (plan step 7)."""
    return card.choice is not CardChoice.NONE or in_anki(card)


def keeps_word(word: WordState) -> bool:
    return decision_status(word) is not DecisionStatus.NEW or any(
        is_protected(card) for card in word.cards
    )


def in_export_queue(word: WordState, lemma: LemmaKnowledge, now: datetime) -> bool:
    """A Learn not in Anki yet, unless its lemma was put in Known after it (Q15)."""
    return decision_status(word) is DecisionStatus.LEARN and not decision_reads_known(
        word, lemma, now,
    )


CHOSEN_TO_LEARN: frozenset[DecisionStatus] = frozenset(
    {DecisionStatus.LEARN, DecisionStatus.LEARNING},
)


def chosen_to_learn(word: WordState) -> bool:
    return decision_status(word) in CHOSEN_TO_LEARN


def section(view: CardView, open_section: CandidateSection) -> CandidateSection:
    """REVIEWED for a done card; an open card keeps the section its phrase earns."""
    return CandidateSection.REVIEWED if view.is_done else open_section


def progress(sections: Iterable[CandidateSection]) -> DecisionProgress:
    """Reviewed / (Reviewed + open Ready)."""
    listed = list(sections)
    reviewed = listed.count(CandidateSection.REVIEWED)
    return DecisionProgress(
        decided=reviewed, total=reviewed + listed.count(CandidateSection.READY),
    )

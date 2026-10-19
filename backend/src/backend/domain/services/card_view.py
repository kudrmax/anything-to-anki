"""What a card shows, derived from the decision tables and `status_of` (design §2.9)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

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
    is_skipped,
    reads_known,
    status_of,
)
from backend.domain.value_objects.card_note import CardNote
from backend.domain.value_objects.decision_progress import DecisionProgress, ReviewReach
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.learning_timer import known_on
from backend.domain.value_objects.user_work import NO_USER_WORK
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from datetime import datetime

    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
    from backend.domain.value_objects.user_work import UserWork


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


class ShownTone(StrEnum):
    """How a done card reads at a glance: open, chosen to learn, or settled (known, or
    the phrase skipped while the word is open)."""

    OPEN = "open"
    LEARNING = "learning"
    SETTLED = "settled"


# The word's decision beats the phrase's Skip.
_TONES: Mapping[tuple[WordStatus, bool], ShownTone] = MappingProxyType(
    {  # (the status shown, the phrase is skipped)
        (WordStatus.NEW, False): ShownTone.OPEN,
        (WordStatus.NEW, True): ShownTone.SETTLED,
        (WordStatus.LEARN, False): ShownTone.LEARNING,
        (WordStatus.LEARN, True): ShownTone.LEARNING,
        (WordStatus.LEARNING, False): ShownTone.LEARNING,
        (WordStatus.LEARNING, True): ShownTone.LEARNING,
        (WordStatus.KNOWN, False): ShownTone.SETTLED,
        (WordStatus.KNOWN, True): ShownTone.SETTLED,
    },
)


@dataclass(frozen=True)
class Shown:
    status: WordStatus
    skipped: bool
    where: Where

    @property
    def tone(self) -> ShownTone:
        return _TONES[(self.status, self.skipped)]


@dataclass(frozen=True)
class CardView:
    card_id: int
    buttons: tuple[ButtonState, ...]
    can_edit_cloze: bool
    note: CardNote | None
    known_on: datetime | None     # when a card in Anki reads Known by its timer
    shown: Shown
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
        pressed=button is shown_press or (button is Press.SKIP and is_skipped(card)),
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
    decided_known: bool = False         # normalised: OTHER cards, the word reads Known


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
        and (not key.decided_known or key.role is Role.OTHER)
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
            NoteRow(CardNote.LEARNED_ON_OTHER_CARD),
        NoteKey(Role.OTHER, False, False, False, False, None, decided_known=True):
            NoteRow(CardNote.KNOWN_ON_OTHER_CARD),
        NoteKey(Role.DECISION, False, False, False, False, None): NoteRow(None),
        NoteKey(Role.DECISION, False, True, False, False, None): NoteRow(None),
        NoteKey(Role.DECISION, True, False, False, False, None):
            NoteRow(CardNote.IN_ANKI, dated=True),
        NoteKey(Role.DECISION, True, True, False, False, None): NoteRow(CardNote.IN_ANKI),
        NoteKey(Role.DECISION, True, False, True, False, None): NoteRow(CardNote.KNOWN_BY_TIMER),
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
        decided_known=role is Role.OTHER and status_of(word, lemma, now) is WordStatus.KNOWN,
    )


def _known_on(card: CardState, row: NoteRow) -> datetime | None:
    binding = card.binding
    return known_on(binding.learning_since) if row.dated and binding else None


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
        skipped=is_skipped(card),
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
        wants_generation=(
            (role is Role.DECISION and in_export_queue(word, lemma, now))
            or (role is Role.OPEN and card.choice is CardChoice.NONE and open_elsewhere is None)
        ),
    )


def open_elsewhere(word: WordState, lemma: LemmaKnowledge) -> ElsewhereStatus | None:
    """What other sources hold of a word open here; a decided word holds its own decision."""
    return lemma.elsewhere if word.decision_card is None else None


def is_decided(word: WordState) -> bool:
    return stored_decided(_STORED[decision_status(word)])


def is_protected(card: CardState, work: UserWork) -> bool:
    """Rebuild never changes nor deletes the card: the user chose on it, it is in Anki, or
    the user made something of it."""
    return card.choice is not CardChoice.NONE or in_anki(card) or work.any


def keeps_word(word: WordState, work: Mapping[int, UserWork]) -> bool:
    """`work`: the user's work by card id; a card not in it has none."""
    return is_decided(word) or any(
        is_protected(card, work.get(card.card_id, NO_USER_WORK)) for card in word.cards
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


# A word's decision status as stored in `candidates.status`, which reads it as a WordStatus.
_STORED: Mapping[DecisionStatus, WordStatus] = MappingProxyType(
    {status: WordStatus(status.value) for status in DecisionStatus},
)


def stored_decided(stored: WordStatus) -> bool:
    """The stored decision status says the word is decided here."""
    return stored is not WordStatus.NEW


def stored_chosen_to_learn(stored: WordStatus) -> bool:
    """`chosen_to_learn` of the word whose stored decision status this is."""
    return DecisionStatus(stored.value) in CHOSEN_TO_LEARN


def card_is_done(stored: WordStatus, skipped: bool, elsewhere: ElsewhereStatus | None) -> bool:
    """A listed card is done when its word is decided, its phrase skipped, or the word is
    known or learned via another source."""
    return stored_decided(stored) or skipped or elsewhere is not None


def learning_in_anki(word: WordState) -> bool:
    """Chosen to learn and exported."""
    return decision_status(word) is DecisionStatus.LEARNING


class Done(Protocol):
    @property
    def is_done(self) -> bool: ...


def section(card: Done, open_section: CandidateSection) -> CandidateSection:
    """REVIEWED for a done card; an open card keeps the section its phrase earns."""
    return CandidateSection.REVIEWED if card.is_done else open_section


def progress(sections: Iterable[CandidateSection]) -> DecisionProgress:
    """Reviewed / (Reviewed + open Ready)."""
    listed = list(sections)
    reviewed = listed.count(CandidateSection.REVIEWED)
    return DecisionProgress(
        decided=reviewed, total=reviewed + listed.count(CandidateSection.READY),
    )


_REACH: Mapping[tuple[bool, bool], ReviewReach] = MappingProxyType(
    {  # (every card that counts is done, none is)
        (True, True): ReviewReach.ALL,
        (True, False): ReviewReach.ALL,
        (False, True): ReviewReach.NONE,
        (False, False): ReviewReach.SOME,
    },
)


def reach(progress: DecisionProgress) -> ReviewReach:
    """How far the review has got; with nothing that counts, it is complete."""
    return _REACH[(progress.decided == progress.total, progress.decided == 0)]

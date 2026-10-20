"""What a card shows, derived from the decision tables and `status_of` (design §2.9)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import product
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.decision_rules import PRESS_RULES, press_key, role_of, rule
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import (
    KIND_OF_CHOICE,
    CardChoice,
    CardState,
    DecisionStatus,
    NoteKind,
    Press,
    Refusal,
    Role,
    WordState,
    decision_reads_known,
    decision_status,
    in_anki,
    is_skipped,
    status_of,
)
from backend.domain.value_objects.decision_progress import DecisionProgress, ReviewReach
from backend.domain.value_objects.elsewhere import ElsewhereStatus
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

    @property
    def is_done(self) -> bool:
        return is_done(self.status, self.skipped)


def is_done(status: WordStatus, skipped: bool) -> bool:
    """The one definition of a done card: its word reads decided, or its phrase is skipped."""
    return status is not WordStatus.NEW or skipped


@dataclass(frozen=True)
class CardView:
    card_id: int
    buttons: tuple[ButtonState, ...]
    can_edit_cloze: bool
    shown: Shown
    wants_generation: bool

    @property
    def is_done(self) -> bool:
        return self.shown.is_done


# --- buttons ----------------------------------------------------------------------------

_COMMANDS: Mapping[tuple[bool, bool], Command | None] = MappingProxyType(
    {  # (refused, opens the cloze editor)
        (True, False): None,
        (False, True): Command.EDIT_CLOZE,
        (False, False): Command.DECIDE,
    },
)
_BOTH = (False, True)
_KINDS: tuple[NoteKind | None, ...] = (None, *NoteKind)
_LEARN_PRESS: Mapping[NoteKind | None, Press] = MappingProxyType(
    {None: Press.LEARN, NoteKind.LEARN: Press.LEARN, NoteKind.CLOZE: Press.CLOZE},
)
_SKIP_PRESS: Mapping[bool, Press | None] = MappingProxyType({False: None, True: Press.SKIP})
PRESSED: Mapping[tuple[WordStatus, bool, NoteKind | None], Press | None] = MappingProxyType({
    # (the status shown, the phrase is skipped, the kind the word's decision card chose)
    **{(WordStatus.NEW, skipped, kind): _SKIP_PRESS[skipped]
       for skipped, kind in product(_BOTH, _KINDS)},
    **{(status, skipped, kind): _LEARN_PRESS[kind]
       for status, skipped, kind in product(
           (WordStatus.LEARN, WordStatus.LEARNING), _BOTH, _KINDS,
       )},
    **{(WordStatus.KNOWN, skipped, kind): Press.KNOWN
       for skipped, kind in product(_BOTH, _KINDS)},
})
"""The button of the status the user sees, on every card of the word: the decision beats
the phrase's Skip, as in the tone."""


def _shown_press(word: WordState, shown: Shown) -> Press | None:
    return rule(
        PRESSED, (shown.status, shown.skipped, KIND_OF_CHOICE.get(word.decision_choice)),
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
        pressed=button is shown_press,
        refused=target.refusal,
    )


def _open_elsewhere(role: Role, elsewhere: ElsewhereStatus | None) -> ElsewhereStatus | None:
    return elsewhere if role is Role.OPEN else None


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
    shown = _shown(word, card, open_elsewhere, lemma, now)
    shown_press = _shown_press(word, shown)
    return CardView(
        card_id=card_id,
        buttons=tuple(
            _button(word, card, button, shown_press, lemma, elsewhere, now) for button in Press
        ),
        can_edit_cloze=card.choice is CardChoice.CLOZE and not in_anki(card),
        shown=shown,
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
    known or learned via another source: done as its card view says."""
    return is_done(_SEEN_ELSEWHERE.get(elsewhere, stored), skipped)


def learning_in_anki(word: WordState) -> bool:
    """Chosen to learn and exported."""
    return decision_status(word) is DecisionStatus.LEARNING


class Done(Protocol):
    @property
    def is_done(self) -> bool: ...


def section(card: Done, open_section: CandidateSection) -> CandidateSection:
    """REVIEWED for a done card; an open card keeps the section its phrase earns."""
    return CandidateSection.REVIEWED if card.is_done else open_section


def shown_section(current: CandidateSection, earned: CandidateSection) -> CandidateSection:
    """Where an open card stands: Ready only when both the section its phrase has now and the
    one it earned are Ready; otherwise the earned one when the current is Ready, else the
    current."""
    if current is CandidateSection.READY and earned is not CandidateSection.READY:
        return earned
    return current


def is_earnable(section: CandidateSection) -> bool:
    """A phrase earns Ready, Extra or Probably known; Reviewed is where a done card stands."""
    return section is not CandidateSection.REVIEWED


def keeps_section(card: CardState) -> bool:
    """A chosen or exported phrase keeps the section it has; a rebuild does not re-stamp it."""
    return card.choice is not CardChoice.NONE or in_anki(card)


def is_ready(section: CandidateSection) -> bool:
    """The section shown on top of review: only the target is new."""
    return section is CandidateSection.READY


def wants_ready_generation(wants_generation: bool, section: CandidateSection) -> bool:
    """✨ for ready phrases makes the card's missing parts: the card wants generation and
    it is shown in Ready (only the target is new), decided or not."""
    return wants_generation and section is CandidateSection.READY


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

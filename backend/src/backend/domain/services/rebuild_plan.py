"""The plan of a lossless rebuild: what a fresh analysis changes in a source's words and
phrases, without losing the user's work."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.domain.services.phrase_protection import is_touched, is_untouchable
from backend.domain.services.phrase_selection import SelectionChange, select_phrases
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.value_objects.built_analysis import (
        BuiltOccurrence,
        BuiltWord,
        WordData,
        WordKey,
    )
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.word_row import WordRow


@dataclass(frozen=True)
class NewWord:
    lemma: str
    is_phrasal_verb: bool
    data: WordData


@dataclass(frozen=True)
class WordUpdate:
    word_id: int
    data: WordData


@dataclass(frozen=True)
class OccurrenceInsert:
    """A new auto phrase of a word, existing or new; `shown`: the selection shows it."""

    word: WordKey
    occurrence: BuiltOccurrence
    shown: bool


@dataclass(frozen=True)
class OccurrenceTextUpdate:
    """A new source phrase for a phrase; its words follow the text the phrase shows."""

    occurrence_id: int
    phrase: Phrase
    phrase_position: DocumentPosition
    fragment_score: float
    bump_revision: bool
    reset_results: bool


@dataclass(frozen=True)
class OccurrenceScoreUpdate:
    occurrence_id: int
    fragment_score: float


@dataclass(frozen=True)
class RebuildCounts:
    """What the user is told about a rebuild.

    `cards_new_phrase`: cards whose phrase moved to one with nothing generated yet;
    `cards_text_reset`: phrases whose generation is dropped because their text changed;
    `cards_without_generation`: shown phrases with nothing generated after the rebuild.
    """

    words_added: int = 0
    words_removed: int = 0
    cards_new_phrase: int = 0
    cards_text_reset: int = 0
    cards_without_generation: int = 0


@dataclass(frozen=True)
class RebuildPlan:
    source_id: int
    words_to_create: tuple[NewWord, ...] = ()
    words_to_update: tuple[WordUpdate, ...] = ()
    words_to_delete: tuple[int, ...] = ()
    occ_to_insert: tuple[OccurrenceInsert, ...] = ()
    occ_to_update_text: tuple[OccurrenceTextUpdate, ...] = ()
    occ_to_update_score: tuple[OccurrenceScoreUpdate, ...] = ()
    occ_to_delete: tuple[int, ...] = ()
    selection_changes: tuple[SelectionChange, ...] = ()
    counts: RebuildCounts = RebuildCounts()

    @property
    def is_empty(self) -> bool:
        """Nothing to change; the counts may still describe the source."""
        return not (
            self.words_to_create or self.words_to_update or self.words_to_delete
            or self.occ_to_insert or self.occ_to_update_text or self.occ_to_update_score
            or self.occ_to_delete or self.selection_changes
        )


def plan_rebuild(
    source_id: int,
    existing: list[OccurrenceRow],
    words: list[WordRow],
    built: list[BuiltWord],
    include_open: bool,
) -> RebuildPlan:
    """Match a fresh analysis to the stored words and phrases of a source.

    Auto phrases match by their key, keeping their ids; manual, example and collected ones
    are not part of the plan, and an auto occurrence where the word already has one of
    them is not created. Untouchable phrases keep everything; a touched phrase with the
    same text gets its new score, and its new words unless polished; a touched phrase whose
    text changed waits for `include_open` (then its revision goes up and its results are
    reset); an untouched phrase gets everything. Occurrences the analysis no longer has go
    unless touched — with `include_open`, unless untouchable. A word with no phrase and no
    decision left goes. The selection then runs on what is left.
    """
    planner = _Planner(include_open)
    rows_by_word: dict[int, list[OccurrenceRow]] = {}
    for o in existing:
        rows_by_word.setdefault(o.candidate_id, []).append(o)
    built_by_key: dict[WordKey, BuiltWord] = {}
    for b in built:
        built_by_key.setdefault(b.key, b)
    known_keys: set[WordKey] = set()
    for w in sorted(words, key=lambda w: w.id):
        known_keys.add(w.key)
        planner.word(w, rows_by_word.get(w.id, []), built_by_key.get(w.key))
    for key, b in built_by_key.items():
        if key not in known_keys:
            planner.new_word(b)
    return planner.plan(source_id)


class _Planner:
    """Collects the plan word by word."""

    def __init__(self, include_open: bool) -> None:
        self._include_open = include_open
        self._new_words: list[NewWord] = []
        self._word_updates: list[WordUpdate] = []
        self._word_deletes: list[int] = []
        self._inserts: list[OccurrenceInsert] = []
        self._text_updates: list[OccurrenceTextUpdate] = []
        self._score_updates: list[OccurrenceScoreUpdate] = []
        self._deletes: list[int] = []
        self._selection: list[SelectionChange] = []
        self._next_placeholder = -1
        self._new_phrase = 0
        self._text_reset = 0
        self._without_generation = 0

    def plan(self, source_id: int) -> RebuildPlan:
        return RebuildPlan(
            source_id=source_id,
            words_to_create=tuple(self._new_words),
            words_to_update=tuple(self._word_updates),
            words_to_delete=tuple(self._word_deletes),
            occ_to_insert=tuple(self._inserts),
            occ_to_update_text=tuple(self._text_updates),
            occ_to_update_score=tuple(self._score_updates),
            occ_to_delete=tuple(self._deletes),
            selection_changes=tuple(self._selection),
            counts=RebuildCounts(
                words_added=len(self._new_words),
                words_removed=len(self._word_deletes),
                cards_new_phrase=self._new_phrase,
                cards_text_reset=self._text_reset,
                cards_without_generation=self._without_generation,
            ),
        )

    def word(self, w: WordRow, rows: list[OccurrenceRow], b: BuiltWord | None) -> None:
        analysed = _by_key(b)
        after: list[OccurrenceRow] = []
        for o in sorted(rows, key=lambda o: o.id):
            kept = self._phrase(o, analysed.get(o.key) if o.key is not None else None, w)
            if kept is not None:
                after.append(kept)
        taken = {o.key for o in rows if o.key is not None}
        fresh = [occ for key, occ in analysed.items() if key not in taken]
        if not w.decided and not after and not fresh:
            self._word_deletes.append(w.id)
            return
        if b is not None and b.data != w.data:
            self._word_updates.append(WordUpdate(word_id=w.id, data=b.data))
        self._select(w.key, w.id, w.decided, rows, after, fresh)

    def new_word(self, b: BuiltWord) -> None:
        fresh = list(_by_key(b).values())
        if not fresh:
            return
        self._new_words.append(NewWord(
            lemma=b.lemma, is_phrasal_verb=b.is_phrasal_verb, data=b.data,
        ))
        self._select(b.key, None, False, [], [], fresh)

    def _phrase(
        self, o: OccurrenceRow, analysed: BuiltOccurrence | None, w: WordRow,
    ) -> OccurrenceRow | None:
        """The phrase as the plan leaves it, or None when the plan deletes it."""
        if o.origin is not OccurrenceOrigin.AUTO or is_untouchable(o):
            return o
        touched = is_touched(o, w.decided)
        if analysed is None:
            if touched and not self._include_open:
                return o
            self._deletes.append(o.id)
            return None
        same_text = o.text_hash == OccurrenceRow.hash_text(analysed.phrase.text)
        new_phrase = OccurrenceRow.hash_phrase(analysed.phrase, analysed.phrase_position)
        if not touched or (same_text and not o.shows_polish):
            if o.phrase_hash != new_phrase:
                return self._rewrite(o, analysed, bump=not same_text, reset=False)
            return self._rescore(o, analysed.fragment_score)
        if same_text:
            return self._rescore(o, analysed.fragment_score)
        if not self._include_open:
            return o
        if o.has_results or o.has_active_job:
            self._text_reset += 1
        return self._rewrite(o, analysed, bump=True, reset=True)

    def _rewrite(
        self, o: OccurrenceRow, analysed: BuiltOccurrence, *, bump: bool, reset: bool,
    ) -> OccurrenceRow:
        self._text_updates.append(OccurrenceTextUpdate(
            occurrence_id=o.id,
            phrase=analysed.phrase,
            phrase_position=analysed.phrase_position,
            fragment_score=analysed.fragment_score,
            bump_revision=bump,
            reset_results=reset,
        ))
        return replace(
            o,
            text_hash=OccurrenceRow.hash_text(analysed.phrase.text),
            phrase_hash=OccurrenceRow.hash_phrase(analysed.phrase, analysed.phrase_position),
            fragment_score=analysed.fragment_score,
            revision=o.revision + 1 if bump else o.revision,
            has_results=False if reset else o.has_results,
            shows_polish=False if reset else o.shows_polish,
        )

    def _rescore(self, o: OccurrenceRow, score: float) -> OccurrenceRow:
        if o.fragment_score == score:
            return o
        self._score_updates.append(OccurrenceScoreUpdate(occurrence_id=o.id, fragment_score=score))
        return replace(o, fragment_score=score)

    def _select(
        self,
        key: WordKey,
        word_id: int | None,
        decided: bool,
        before: list[OccurrenceRow],
        after: list[OccurrenceRow],
        fresh: list[BuiltOccurrence],
    ) -> None:
        placeholders = {self._placeholder(): occ for occ in fresh}
        candidates = after + [
            _fresh_row(placeholder, word_id or 0, occ) for placeholder, occ in placeholders.items()
        ]
        change = select_phrases(candidates, decided, self._include_open)
        chosen = change.set_selection
        for placeholder, occ in placeholders.items():
            self._inserts.append(OccurrenceInsert(
                word=key, occurrence=occ, shown=placeholder == chosen,
            ))
        existing_choice = chosen if chosen is not None and chosen > 0 else None
        kept = SelectionChange(
            set_selection=existing_choice, clear_selection=change.clear_selection,
        )
        if not kept.is_empty:
            self._selection.append(kept)
        self._count(before, candidates, change)

    def _count(
        self,
        before: list[OccurrenceRow],
        after: list[OccurrenceRow],
        change: SelectionChange,
    ) -> None:
        cleared = set(change.clear_selection)
        shown_after = [
            o for o in after
            if (o.is_shown and o.id not in cleared) or o.id == change.set_selection
        ]
        self._without_generation += sum(1 for o in shown_after if not o.has_results)
        had_selection = any(o.shown_by is ShownBy.SELECTION for o in before)
        chosen = next((o for o in after if o.id == change.set_selection), None)
        if had_selection and chosen is not None and not chosen.has_results:
            self._new_phrase += 1

    def _placeholder(self) -> int:
        """An id for a phrase not stored yet; stored ids are positive."""
        placeholder = self._next_placeholder
        self._next_placeholder -= 1
        return placeholder


def _by_key(b: BuiltWord | None) -> dict[OccurrenceKey, BuiltOccurrence]:
    analysed: dict[OccurrenceKey, BuiltOccurrence] = {}
    if b is not None:
        for occ in b.occurrences:
            analysed.setdefault(occ.key, occ)
    return analysed


def _fresh_row(placeholder: int, word_id: int, occ: BuiltOccurrence) -> OccurrenceRow:
    return OccurrenceRow(
        id=placeholder,
        candidate_id=word_id,
        key=occ.key,
        origin=OccurrenceOrigin.AUTO,
        shown_by=None,
        skipped=False,
        is_decision=False,
        revision=0,
        edited_by_user=False,
        has_results=False,
        exported=False,
        has_active_job=False,
        text_hash=OccurrenceRow.hash_text(occ.phrase.text),
        fragment_score=occ.fragment_score,
        shows_polish=False,
        phrase_hash=OccurrenceRow.hash_phrase(occ.phrase, occ.phrase_position),
    )

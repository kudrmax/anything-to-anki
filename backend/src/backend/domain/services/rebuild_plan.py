"""The plan of a rebuild: what a fresh analysis changes in a source's words and phrases,
without losing the user's work."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.domain.services.card_view import is_decided, keeps_section, keeps_word
from backend.domain.services.phrase_protection import is_untouchable
from backend.domain.services.phrase_selection import SelectionChange, select_phrases
from backend.domain.value_objects.card_choice import CardChoice, WordState
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_generation import NO_GENERATION
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.rebuild_mode import RebuildMode

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.services.candidate_sections import SectionRule, WordFacts
    from backend.domain.services.phrase_selection import SelectionScore
    from backend.domain.value_objects.built_analysis import (
        BuiltOccurrence,
        BuiltWord,
        WordData,
        WordKey,
    )
    from backend.domain.value_objects.candidate_section import CandidateSection
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
    earned_section: CandidateSection


@dataclass(frozen=True)
class OccurrenceTextUpdate:
    """A new source phrase for a phrase; its words follow the text the phrase shows.

    `bump_revision`: the text changed. `drop_text_generation`: what was made of the old text
    (polish, TTS, video frame and clip) goes."""

    occurrence_id: int
    phrase: Phrase
    phrase_position: DocumentPosition
    fragment_score: float
    bump_revision: bool
    drop_text_generation: bool
    earned_section: CandidateSection


@dataclass(frozen=True)
class SectionChange:
    """A phrase whose stored section a rebuild moves, its text staying as it is."""

    occurrence_id: int
    earned_section: CandidateSection


@dataclass(frozen=True)
class OccurrenceRekey:
    """A phrase found again where its key moved within its line: it takes the new key."""

    occurrence_id: int
    key: OccurrenceKey


@dataclass(frozen=True)
class OccurrenceScoreUpdate:
    occurrence_id: int
    fragment_score: float


@dataclass(frozen=True)
class RebuildCounts:
    """What the user is told about a rebuild.

    `cards_lost_generation`: shown phrases deleted with something made for them;
    `cards_moved`: words whose card moved to a phrase with nothing made for it yet;
    `cards_recut`: phrases cut again; `cards_recut_lost_text_generation`: those of them that
    lose what was made of their old text.
    """

    words_added: int = 0
    words_removed: int = 0
    cards_lost_generation: int = 0
    cards_moved: int = 0
    cards_recut: int = 0
    cards_recut_lost_text_generation: int = 0


@dataclass(frozen=True)
class RebuildRules:
    """How a rebuild goes.

    `sections`: what the user knows, for the sections phrases earn; `score`: how the selection
    weighs a phrase; `done_on_the_fly`: words the user knows or learns via another source —
    their cards already show done, and a rebuild keeps them as they are.
    """

    mode: RebuildMode
    sections: SectionRule
    score: SelectionScore
    done_on_the_fly: frozenset[WordKey] = frozenset()


@dataclass(frozen=True)
class RebuildPlan:
    source_id: int
    words_to_create: tuple[NewWord, ...] = ()
    words_to_update: tuple[WordUpdate, ...] = ()
    words_to_delete: tuple[int, ...] = ()
    occ_to_insert: tuple[OccurrenceInsert, ...] = ()
    occ_to_update_text: tuple[OccurrenceTextUpdate, ...] = ()
    occ_to_update_score: tuple[OccurrenceScoreUpdate, ...] = ()
    occ_to_rekey: tuple[OccurrenceRekey, ...] = ()
    occ_to_delete: tuple[int, ...] = ()
    selection_changes: tuple[SelectionChange, ...] = ()
    section_changes: tuple[SectionChange, ...] = ()
    counts: RebuildCounts = RebuildCounts()

    @property
    def is_empty(self) -> bool:
        """Nothing to change; the counts may still describe the source."""
        return not (
            self.words_to_create or self.words_to_update or self.words_to_delete
            or self.occ_to_insert or self.occ_to_update_text or self.occ_to_update_score
            or self.occ_to_rekey or self.occ_to_delete or self.selection_changes
            or self.section_changes
        )


@dataclass(frozen=True)
class AppliedPlan:
    """What writing a plan did: the ids of the inserted phrases, in the order of
    `occ_to_insert`, and the files of what it dropped, to remove once it is committed."""

    inserted: list[int]
    dropped_files: list[str]


def plan_rebuild(
    source_id: int,
    existing: list[OccurrenceRow],
    words: list[WordRow],
    built: list[BuiltWord],
    rules: RebuildRules,
) -> RebuildPlan:
    """Match a fresh analysis to the stored words and phrases of a source.

    Auto phrases match by their key, keeping their ids; one whose key the analysis does not
    have is the free occurrence of its word on its line with the same text, if there is one
    (its very phrase first, else the nearest), and takes its key — an older analysis or a
    migrated card may have keyed the same place differently. Manual, example and collected
    ones are not part of the plan, and an auto occurrence where the word already has one of
    them is not created.

    Untouchable phrases, and every phrase of a decided word or of a word done on the fly,
    stay as they are. A word the analysis no longer finds loses its other phrases, whatever
    was made for them. Of a word still found:
    - a phrase with the same text gets its new score, and its new words unless polished;
    - a phrase whose text changed is cut again only by a recut, losing what was made of its
      old text;
    - a phrase whose place is gone goes when nothing was made for it, or by a recut; one
      that stays keeps its line free of new phrases of its word.
    A word goes when no phrase is left and nothing keeps it (`keeps_word`). The selection
    then runs on what is left. Each new phrase is stamped with the section it earns, and so
    is every kept phrase without a choice and out of Anki, by the data of its word as the
    analysis leaves it.
    """
    planner = _Planner(source_id, rules)
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
    return planner.plan()


def plan_sections(
    source_id: int,
    existing: list[OccurrenceRow],
    words: list[WordRow],
    rule: SectionRule,
) -> RebuildPlan:
    """Only the sections of a source's phrases, by the data its words have stored."""
    rows_by_word: dict[int, list[OccurrenceRow]] = {}
    for o in existing:
        rows_by_word.setdefault(o.candidate_id, []).append(o)
    changes: list[SectionChange] = []
    for w in sorted(words, key=lambda w: w.id):
        changes.extend(_restamped(rows_by_word.get(w.id, []), w, rule))
    return RebuildPlan(source_id=source_id, section_changes=tuple(changes))


def _restamped(
    rows: list[OccurrenceRow], facts: WordFacts, rule: SectionRule,
) -> list[SectionChange]:
    """The phrases that earn another section now; a chosen or exported one keeps its own."""
    changes: list[SectionChange] = []
    for o in rows:
        if keeps_section(o.card_state):
            continue
        earned = rule.earned(o.shown_phrase, facts)
        if earned != o.earned_section:
            changes.append(SectionChange(occurrence_id=o.id, earned_section=earned))
    return changes


class _Planner:
    """Collects the plan word by word."""

    def __init__(self, source_id: int, rules: RebuildRules) -> None:
        self._source_id = source_id
        self._rules = rules
        self._new_words: list[NewWord] = []
        self._word_updates: list[WordUpdate] = []
        self._word_deletes: list[int] = []
        self._inserts: list[OccurrenceInsert] = []
        self._text_updates: list[OccurrenceTextUpdate] = []
        self._score_updates: list[OccurrenceScoreUpdate] = []
        self._rekeys: list[OccurrenceRekey] = []
        self._deletes: list[int] = []
        self._selection: list[SelectionChange] = []
        self._sections: list[SectionChange] = []
        self._rewritten: set[int] = set()
        self._next_placeholder = -1
        self._lost_generation = 0
        self._moved = 0
        self._recut = 0
        self._recut_lost = 0

    def plan(self) -> RebuildPlan:
        return RebuildPlan(
            source_id=self._source_id,
            words_to_create=tuple(self._new_words),
            words_to_update=tuple(self._word_updates),
            words_to_delete=tuple(self._word_deletes),
            occ_to_insert=tuple(self._inserts),
            occ_to_update_text=tuple(self._text_updates),
            occ_to_update_score=tuple(self._score_updates),
            occ_to_rekey=tuple(self._rekeys),
            occ_to_delete=tuple(self._deletes),
            selection_changes=tuple(self._selection),
            section_changes=tuple(self._sections),
            counts=RebuildCounts(
                words_added=len(self._new_words),
                words_removed=len(self._word_deletes),
                cards_lost_generation=self._lost_generation,
                cards_moved=self._moved,
                cards_recut=self._recut,
                cards_recut_lost_text_generation=self._recut_lost,
            ),
        )

    def word(self, w: WordRow, rows: list[OccurrenceRow], b: BuiltWord | None) -> None:
        analysed = _by_key(b)
        rows = [self._found_again(o) for o in _moved_keys(rows, analysed)]
        state = WordState(
            w.id, w.lemma, w.data.pos, self._source_id, tuple(o.card_state for o in rows),
        )
        decided = is_decided(state)
        facts = b if b is not None else w
        if decided or w.key in self._rules.done_on_the_fly:
            after = rows
        else:
            after = [
                kept for o in sorted(rows, key=lambda o: o.id)
                if (kept := self._phrase(o, _analysed_at(o, analysed), facts, b is None))
                is not None
            ]
        self._sections.extend(
            _restamped(
                [o for o in after if o.id not in self._rewritten], facts, self._rules.sections,
            ),
        )
        fresh = _fresh_places(rows, after, analysed)
        if not keeps_word(state, {o.id: o.user_work for o in rows}) and not after and not fresh:
            self._word_deletes.append(w.id)
            return
        if b is not None and b.data != w.data:
            self._word_updates.append(WordUpdate(word_id=w.id, data=b.data))
        self._select(w.key, w.id, decided, rows, after, _Fresh(b, fresh))

    def new_word(self, b: BuiltWord) -> None:
        fresh = list(_by_key(b).values())
        if not fresh:
            return
        self._new_words.append(NewWord(
            lemma=b.lemma, is_phrasal_verb=b.is_phrasal_verb, data=b.data,
        ))
        self._select(b.key, None, False, [], [], _Fresh(b, fresh))

    def _found_again(self, moved: tuple[OccurrenceRow, OccurrenceKey | None]) -> OccurrenceRow:
        o, key = moved
        if key is None:
            return o
        assert o.id > 0
        self._rekeys.append(OccurrenceRekey(occurrence_id=o.id, key=key))
        return replace(o, key=key)

    def _phrase(
        self,
        o: OccurrenceRow,
        analysed: BuiltOccurrence | None,
        facts: WordFacts,
        word_gone: bool,
    ) -> OccurrenceRow | None:
        """The phrase as the plan leaves it, or None when the plan deletes it."""
        if o.origin is not OccurrenceOrigin.AUTO or is_untouchable(o):
            return o
        if analysed is None:
            if word_gone or self._recuts or not (o.generation.any or o.has_active_job):
                self._delete(o)
                return None
            return o
        if o.text_hash == OccurrenceRow.hash_text(analysed.phrase.text):
            if not o.shows_polish and o.phrase_hash != _phrase_hash(analysed):
                return self._rewrite(o, analysed, facts, recut=False)
            return self._rescore(o, analysed.fragment_score)
        if not self._recuts:
            return o
        self._recut += 1
        if o.generation.of_text:
            self._recut_lost += 1
        return self._rewrite(o, analysed, facts, recut=True)

    @property
    def _recuts(self) -> bool:
        return self._rules.mode is RebuildMode.RECUT

    def _delete(self, o: OccurrenceRow) -> None:
        if o.is_shown and o.generation.any:
            self._lost_generation += 1
        self._deletes.append(o.id)

    def _rewrite(
        self,
        o: OccurrenceRow,
        analysed: BuiltOccurrence,
        facts: WordFacts,
        *,
        recut: bool,
    ) -> OccurrenceRow:
        """A new source phrase: by a recut, a new text, losing what was made of the old one;
        else the same text with new facts about its words, the phrase showing it."""
        assert recut or not o.shows_polish, "a polished phrase keeps its source phrase"
        drop = recut and o.generation.of_text
        earned = self._rules.sections.earned(analysed.phrase, facts)
        self._rewritten.add(o.id)
        self._text_updates.append(OccurrenceTextUpdate(
            occurrence_id=o.id,
            phrase=analysed.phrase,
            phrase_position=analysed.phrase_position,
            fragment_score=analysed.fragment_score,
            bump_revision=recut,
            drop_text_generation=drop,
            earned_section=earned,
        ))
        generation = (
            replace(o.generation, polish=False, text_media=False) if drop else o.generation
        )
        return replace(
            o,
            text_hash=OccurrenceRow.hash_text(analysed.phrase.text),
            phrase_hash=_phrase_hash(analysed),
            fragment_score=analysed.fragment_score,
            revision=o.revision + 1 if recut else o.revision,
            generation=generation,
            shows_polish=False,
            source_phrase=analysed.phrase,
            shown_phrase=analysed.phrase,
            earned_section=earned,
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
        fresh: _Fresh,
    ) -> None:
        placeholders = {self._placeholder(): occ for occ in fresh.occurrences}
        earned = {
            placeholder: self._rules.sections.earned(occ.phrase, fresh.word)
            for placeholder, occ in placeholders.items()
            if fresh.word is not None
        }
        candidates = after + [
            _fresh_row(placeholder, word_id or 0, occ, earned[placeholder])
            for placeholder, occ in placeholders.items()
        ]
        change = select_phrases(candidates, decided, self._rules.score)
        chosen = change.set_selection
        for placeholder, occ in placeholders.items():
            assert fresh.word is not None
            self._inserts.append(OccurrenceInsert(
                word=key,
                occurrence=occ,
                shown=placeholder == chosen,
                earned_section=earned[placeholder],
            ))
        existing_choice = chosen if chosen is not None and chosen > 0 else None
        kept = SelectionChange(
            set_selection=existing_choice, clear_selection=change.clear_selection,
        )
        if not kept.is_empty:
            self._selection.append(kept)
        self._count_move(before, candidates, change)

    def _count_move(
        self,
        before: list[OccurrenceRow],
        after: list[OccurrenceRow],
        change: SelectionChange,
    ) -> None:
        had_selection = any(o.shown_by is ShownBy.SELECTION for o in before)
        chosen = next((o for o in after if o.id == change.set_selection), None)
        if had_selection and chosen is not None and not chosen.generation.any:
            self._moved += 1

    def _placeholder(self) -> int:
        """An id for a phrase not stored yet; stored ids are positive."""
        placeholder = self._next_placeholder
        self._next_placeholder -= 1
        return placeholder


@dataclass(frozen=True)
class _Fresh:
    """The phrases the analysis found anew for a word, with the word they belong to."""

    word: BuiltWord | None
    occurrences: list[BuiltOccurrence]


def _moved_keys(
    rows: list[OccurrenceRow], analysed: dict[OccurrenceKey, BuiltOccurrence],
) -> list[tuple[OccurrenceRow, OccurrenceKey | None]]:
    """Every phrase with the key it is found at again, when its own key is not analysed: an
    occurrence on its line with its text that no phrase of the word holds — the one with its
    very phrase (the same target) first, then the nearest."""
    held = {o.key for o in rows if o.key is not None}
    free = [key for key in analysed if key not in held]
    moved: list[tuple[OccurrenceRow, OccurrenceKey | None]] = []
    for o in sorted(rows, key=lambda o: o.id):
        if o.origin is not OccurrenceOrigin.AUTO or o.key is None or o.key in analysed:
            moved.append((o, None))
            continue
        own = o.key
        same_place = [
            key for key in free
            if (key.block, key.line) == (own.block, own.line)
            and OccurrenceRow.hash_text(analysed[key].phrase.text) == o.text_hash
        ]
        found = min(
            same_place,
            key=lambda key: (
                _phrase_hash(analysed[key]) != o.phrase_hash,
                abs(key.char - own.char),
                key.char,
            ),
            default=None,
        )
        if found is not None:
            free.remove(found)
        moved.append((o, found))
    return moved


def _analysed_at(
    o: OccurrenceRow, analysed: dict[OccurrenceKey, BuiltOccurrence],
) -> BuiltOccurrence | None:
    return analysed.get(o.key) if o.key is not None else None


def _fresh_places(
    rows: list[OccurrenceRow],
    after: list[OccurrenceRow],
    analysed: dict[OccurrenceKey, BuiltOccurrence],
) -> list[BuiltOccurrence]:
    """The analysed places of a word no phrase holds yet; a kept phrase whose place the
    analysis no longer has holds its line, so the place gets no second phrase."""
    taken = {o.key for o in rows if o.key is not None}
    held_lines = {
        (o.key.block, o.key.line) for o in after
        if o.key is not None and o.key not in analysed and o.origin is OccurrenceOrigin.AUTO
    }
    return [
        occ for key, occ in analysed.items()
        if key not in taken and (key.block, key.line) not in held_lines
    ]


def _phrase_hash(occ: BuiltOccurrence) -> str:
    return OccurrenceRow.hash_phrase(occ.phrase, occ.phrase_position)


def _by_key(b: BuiltWord | None) -> dict[OccurrenceKey, BuiltOccurrence]:
    analysed: dict[OccurrenceKey, BuiltOccurrence] = {}
    if b is not None:
        for occ in b.occurrences:
            analysed.setdefault(occ.key, occ)
    return analysed


def _fresh_row(
    placeholder: int, word_id: int, occ: BuiltOccurrence, earned: CandidateSection,
) -> OccurrenceRow:
    return OccurrenceRow(
        id=placeholder,
        candidate_id=word_id,
        key=occ.key,
        origin=OccurrenceOrigin.AUTO,
        shown_by=None,
        choice=CardChoice.NONE,
        revision=0,
        edited_by_user=False,
        generation=NO_GENERATION,
        binding=None,
        has_active_job=False,
        text_hash=OccurrenceRow.hash_text(occ.phrase.text),
        fragment_score=occ.fragment_score,
        shows_polish=False,
        phrase_hash=OccurrenceRow.hash_phrase(occ.phrase, occ.phrase_position),
        source_phrase=occ.phrase,
        shown_phrase=occ.phrase,
        earned_section=earned,
    )

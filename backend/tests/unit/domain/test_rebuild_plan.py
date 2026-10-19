"""The rebuild plan: what a re-analysis changes in the words and phrases of a source,
and that it never loses the user's work."""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

import pytest
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.services.candidate_sections import SectionRule
from backend.domain.services.phrase_protection import is_touched, is_untouchable
from backend.domain.services.phrase_selection import is_frozen, select_phrases
from backend.domain.services.rebuild_plan import OccurrenceRekey, RebuildPlan, plan_rebuild
from backend.domain.value_objects.built_analysis import BuiltOccurrence, BuiltWord, WordKey
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY
from backend.domain.value_objects.word_row import WordRow
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import phrase
from tests.rebuild_support import (
    AUTO,
    COLLECTED,
    EXAMPLE,
    MANUAL,
    READY_RULE,
    SELECTION,
    USER,
    breakdown,
    built,
    key_at,
    occ,
    position_at,
    row,
    text_phrase,
    word,
)

SOURCE = 7
GENERATED_CASES = 40
TEXTS = ("He glared at me.", "She glared back.", "They glared and left.")
SCORES = (0.1, 0.2, 0.5, None)
KEY_LINES = 5


def _decided(w: WordRow) -> bool:
    """The stored status, as the oracle for what the plan derives from the cards."""
    return w.status is not WordStatus.NEW


def plan(
    existing: list[OccurrenceRow],
    words: list[WordRow],
    analysed: list[BuiltWord],
    *,
    include_open: bool = False,
) -> RebuildPlan:
    return plan_rebuild(SOURCE, existing, words, analysed, include_open, READY_RULE)


# ── an in-memory store that applies a plan the way the repository does ─────────


@dataclass
class Store:
    rows: dict[int, OccurrenceRow]
    words: dict[int, WordRow]
    next_id: int = 1000
    texts: dict[int, tuple[str, bool]] = field(default_factory=dict)

    def apply(self, plan: RebuildPlan) -> None:
        for word_id in plan.words_to_delete:
            del self.words[word_id]
        for update in plan.words_to_update:
            self.words[update.word_id] = replace(self.words[update.word_id], data=update.data)
        for new in plan.words_to_create:
            self.next_id += 1
            self.words[self.next_id] = WordRow(
                id=self.next_id, lemma=new.lemma, is_phrasal_verb=new.is_phrasal_verb,
                status=WordStatus.NEW, data=new.data,
            )
        for occurrence_id in plan.occ_to_delete:
            del self.rows[occurrence_id]
        for rekey in plan.occ_to_rekey:
            self.rows[rekey.occurrence_id] = replace(self.rows[rekey.occurrence_id], key=rekey.key)
        for text_update in plan.occ_to_update_text:
            old = self.rows[text_update.occurrence_id]
            reset = text_update.reset_results
            self.rows[old.id] = replace(
                old,
                text_hash=OccurrenceRow.hash_text(text_update.phrase.text),
                phrase_hash=OccurrenceRow.hash_phrase(
                    text_update.phrase, text_update.phrase_position,
                ),
                fragment_score=text_update.fragment_score,
                revision=old.revision + (1 if text_update.bump_revision else 0),
                has_results=False if reset else old.has_results,
                shows_polish=False if reset else old.shows_polish,
            )
        for score in plan.occ_to_update_score:
            self.rows[score.occurrence_id] = replace(
                self.rows[score.occurrence_id], fragment_score=score.fragment_score,
            )
        ids_by_key = {w.key: w.id for w in self.words.values()}
        for insert in plan.occ_to_insert:
            self.next_id += 1
            o = insert.occurrence
            self.rows[self.next_id] = OccurrenceRow(
                id=self.next_id, candidate_id=ids_by_key[insert.word], key=o.key,
                origin=OccurrenceOrigin.AUTO,
                shown_by=ShownBy.SELECTION if insert.shown else None,
                choice=CardChoice.NONE, revision=0, edited_by_user=False,
                has_results=False, binding=None, has_active_job=False,
                text_hash=OccurrenceRow.hash_text(o.phrase.text),
                fragment_score=o.fragment_score, shows_polish=False, replaces_selection=False,
                phrase_hash=OccurrenceRow.hash_phrase(o.phrase, o.phrase_position),
            )
        for change in plan.selection_changes:
            for cleared in change.clear_selection:
                self.rows[cleared] = replace(self.rows[cleared], shown_by=None)
            if change.set_selection is not None:
                self.rows[change.set_selection] = replace(
                    self.rows[change.set_selection], shown_by=ShownBy.SELECTION,
                )
        live = set(self.words)
        self.rows = {i: r for i, r in self.rows.items() if r.candidate_id in live}

    def plan(self, analysed: list[BuiltWord], include_open: bool) -> RebuildPlan:
        return plan_rebuild(
            SOURCE, list(self.rows.values()), list(self.words.values()), analysed, include_open,
            READY_RULE,
        )


# ── random sources ───────────────────────────────────────────────────────────


def _random_row(rnd: random.Random, row_id: int, word_id: int, line: int) -> OccurrenceRow:
    origin = rnd.choice([AUTO] * 6 + [MANUAL, EXAMPLE, COLLECTED])
    shown = rnd.choice([None, None, SELECTION, USER]) if origin is AUTO else USER
    return row(
        id=row_id, candidate_id=word_id, line=line, score=rnd.choice(SCORES),
        shown=shown, origin=origin,
        skipped=rnd.random() < 0.15,
        edited=rnd.random() < 0.1,
        has_results=rnd.random() < 0.25,
        exported=rnd.random() < 0.05,
        has_job=rnd.random() < 0.1,
        text=rnd.choice(TEXTS),
        variant=rnd.random() < 0.3,
        shows_polish=rnd.random() < 0.15,
        replaces=shown is USER and rnd.random() < 0.4,
    )


def random_source(seed: int) -> tuple[list[OccurrenceRow], list[WordRow], list[BuiltWord]]:
    rnd = random.Random(seed)
    rows: list[OccurrenceRow] = []
    words: list[WordRow] = []
    next_row = 1
    for word_id in range(1, rnd.randint(2, 6)):
        status = rnd.choice([WordStatus.NEW] * 3 + [WordStatus.LEARN, WordStatus.KNOWN])
        words.append(word(word_id, f"w{word_id}", status=status, count=rnd.randint(1, 3)))
        used: set[tuple[OccurrenceOrigin, int]] = set()
        for _ in range(rnd.randint(0, 4)):
            candidate = _random_row(rnd, next_row, word_id, rnd.randrange(KEY_LINES))
            slot = (
                OccurrenceOrigin.AUTO if candidate.origin is AUTO else OccurrenceOrigin.MANUAL,
                candidate.key.line if candidate.key else -1,
            )
            if slot in used:
                continue
            used.add(slot)
            rows.append(candidate)
            next_row += 1
        mine = [r for r in rows if r.candidate_id == word_id]
        if status is not WordStatus.NEW:
            if not mine:
                rows.append(row(id=next_row, candidate_id=word_id, origin=MANUAL, shown=USER))
                next_row += 1
                mine = rows[-1:]
            chosen = rnd.choice(mine)
            rows[rows.index(chosen)] = replace(chosen, choice=CardChoice.LEARN)
    analysed: list[BuiltWord] = []
    lemmas = [w.lemma for w in words] + [f"new{i}" for i in range(rnd.randint(0, 2))]
    for lemma in lemmas:
        if rnd.random() < 0.3:
            continue
        lines = rnd.sample(range(KEY_LINES), rnd.randint(1, 3))
        analysed.append(built(lemma, *(
            occ(line, rnd.choice((0.1, 0.2, 0.5)), text=rnd.choice(TEXTS),
                variant=rnd.random() < 0.3)
            for line in sorted(lines)
        ), zipf=rnd.choice((3.0, 4.0))))
    return rows, words, analysed


CASES = [(seed, include_open) for seed in range(GENERATED_CASES) for include_open in (False, True)]


@pytest.mark.parametrize(("seed", "include_open"), CASES)
def test_rebuilding_twice_gives_an_empty_plan(seed: int, include_open: bool) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})

    store.apply(store.plan(analysed, include_open))

    assert store.plan(analysed, include_open).is_empty


@pytest.mark.parametrize(("seed", "include_open"), CASES)
def test_untouchable_phrases_are_never_deleted_nor_changed(
    seed: int, include_open: bool,
) -> None:
    rows, words, analysed = random_source(seed)
    untouchable = {r.id for r in rows if is_untouchable(r)}

    result = plan_rebuild(SOURCE, rows, words, analysed, include_open, READY_RULE)

    changed = (
        set(result.occ_to_delete)
        | {u.occurrence_id for u in result.occ_to_update_text}
        | {u.occurrence_id for u in result.occ_to_update_score}
    )
    assert not changed & untouchable
    words_of_untouchable = {r.candidate_id for r in rows if r.id in untouchable}
    assert not set(result.words_to_delete) & words_of_untouchable


@pytest.mark.parametrize("seed", range(GENERATED_CASES))
def test_without_include_open_touched_phrases_stay_and_keep_their_text(seed: int) -> None:
    rows, words, analysed = random_source(seed)
    decided = {w.id for w in words if _decided(w)}
    touched = {r.id for r in rows if is_touched(r, r.candidate_id in decided)}
    text_of = {r.id: r.text_hash for r in rows}

    result = plan_rebuild(SOURCE, rows, words, analysed, False, READY_RULE)

    assert not set(result.occ_to_delete) & touched
    for update in result.occ_to_update_text:
        if update.occurrence_id in touched:
            assert OccurrenceRow.hash_text(update.phrase.text) == text_of[update.occurrence_id]
            assert not update.reset_results


@pytest.mark.parametrize(("seed", "include_open"), CASES)
def test_decided_words_are_never_removed(seed: int, include_open: bool) -> None:
    rows, words, analysed = random_source(seed)

    result = plan_rebuild(SOURCE, rows, words, analysed, include_open, READY_RULE)

    assert not set(result.words_to_delete) & {w.id for w in words if _decided(w)}


@pytest.mark.parametrize(("seed", "include_open"), CASES)
def test_after_a_rebuild_selection_holds_its_invariant(seed: int, include_open: bool) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})
    before = dict(store.rows)

    store.apply(store.plan(analysed, include_open))

    for kept_id, kept in store.rows.items():
        if kept_id in before and before[kept_id].shown_by is USER:
            assert kept.shown_by is USER
    for w in store.words.values():
        mine = [r for r in store.rows.values() if r.candidate_id == w.id]
        assert select_phrases(mine, _decided(w), include_open).is_empty
        if _decided(w):
            continue
        selected = [r for r in mine if r.shown_by is SELECTION]
        loose = [r for r in selected if not is_frozen(r, include_open)]
        assert all(r.origin is AUTO for r in selected)
        assert len(loose) <= 1
        assert not loose or len(selected) == 1


@pytest.mark.parametrize(("seed", "include_open"), CASES)
def test_words_without_phrases_and_decision_go(seed: int, include_open: bool) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})

    store.apply(store.plan(analysed, include_open))

    for w in store.words.values():
        assert _decided(w) or any(r.candidate_id == w.id for r in store.rows.values())


# ── the rules one by one ────────────────────────────────────────────────────


def test_a_new_word_is_created_with_its_best_phrase_shown() -> None:
    result = plan([], [], [built("glare", occ(0, 0.5), occ(1, 0.1))])

    assert [w.lemma for w in result.words_to_create] == ["glare"]
    assert [(i.occurrence.key, i.shown) for i in result.occ_to_insert] == [
        (key_at(0), False), (key_at(1), True),
    ]
    assert result.counts.words_added == 1


def test_a_manual_phrase_blocks_a_later_auto_phrase_at_its_place() -> None:
    manual = row(id=1, line=2, origin=MANUAL, shown=USER)

    result = plan([manual], [word()], [built("glare", occ(2, 0.1))])

    assert result.occ_to_insert == ()
    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()


def test_auto_phrases_match_by_key_and_keep_their_ids() -> None:
    old = row(id=5, line=3, score=0.5, shown=SELECTION)

    result = plan([old], [word()], [built("glare", occ(3, 0.2))])

    assert result.occ_to_insert == ()
    assert [u.occurrence_id for u in result.occ_to_update_score] == [5]
    assert result.occ_to_update_score[0].fragment_score == 0.2


def test_a_decided_word_stays_though_the_analysis_has_lost_it() -> None:
    decision = row(id=1, shown=SELECTION, is_decision=True)
    hidden = row(id=2)

    result = plan([decision, hidden], [word(status=WordStatus.LEARN)], [])

    assert result.words_to_delete == ()
    assert result.occ_to_delete == (2,)


def test_an_untouched_word_the_analysis_lost_goes_with_its_phrases() -> None:
    shown = row(id=1, shown=SELECTION)

    result = plan([shown], [word()], [])

    assert result.words_to_delete == (1,)
    assert result.occ_to_delete == (1,)
    assert result.counts.words_removed == 1


def test_a_word_with_a_touched_phrase_stays_without_include_open() -> None:
    generated = row(id=1, shown=SELECTION, has_results=True)

    assert plan([generated], [word()], []).words_to_delete == ()
    assert plan([generated], [word()], [], include_open=True).words_to_delete == (1,)


def test_include_open_keeps_a_skipped_phrase_the_analysis_lost_and_its_word() -> None:
    skipped = row(id=1, shown=SELECTION, skipped=True, has_results=True)

    result = plan([skipped], [word()], [], include_open=True)

    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()
    assert result.is_empty


def test_include_open_keeps_the_old_text_and_results_of_a_skipped_phrase() -> None:
    skipped = row(id=1, score=0.5, shown=SELECTION, skipped=True, has_results=True)
    analysed = [built("glare", occ(1, 0.5, text="She glared back."))]

    result = plan([skipped], [word()], analysed, include_open=True)

    assert result.occ_to_update_text == ()
    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()
    assert result.counts.cards_text_reset == 0


def test_a_polished_phrase_keeps_its_words() -> None:
    polished = row(id=1, score=0.5, shown=SELECTION, has_results=True, shows_polish=True)

    result = plan([polished], [word()], [built("glare", occ(1, 0.3, variant=True))])

    assert result.occ_to_update_text == ()
    assert [u.occurrence_id for u in result.occ_to_update_score] == [1]


def test_a_touched_phrase_with_the_same_text_gets_its_new_words() -> None:
    touched = row(id=1, score=0.5, shown=SELECTION, has_results=True)

    result = plan([touched], [word()], [built("glare", occ(1, 0.5, variant=True))])

    [update] = result.occ_to_update_text
    assert (update.occurrence_id, update.bump_revision, update.reset_results) == (1, False, False)


def test_changed_text_of_a_touched_phrase_waits_for_include_open() -> None:
    touched = row(id=1, score=0.5, shown=SELECTION, has_results=True)
    analysed = [built("glare", occ(1, 0.5, text="She glared back."))]

    assert plan([touched], [word()], analysed).is_empty

    result = plan([touched], [word()], analysed, include_open=True)
    [update] = result.occ_to_update_text
    assert (update.bump_revision, update.reset_results) == (True, True)
    assert result.counts.cards_text_reset == 1


def test_changed_text_of_an_untouched_phrase_is_rewritten() -> None:
    untouched = row(id=1, score=0.5, shown=SELECTION)

    result = plan([untouched], [word()], [built("glare", occ(1, 0.5, text="She glared back."))])

    [update] = result.occ_to_update_text
    assert update.phrase == text_phrase("She glared back.")
    assert update.phrase_position == position_at(1, "She glared back.")
    assert not update.reset_results


def test_a_rewritten_phrase_carries_the_section_of_its_new_text() -> None:
    untouched = row(id=1, score=0.5, shown=SELECTION)
    new_text = "She glared quill"
    analysed = BuiltOccurrence(
        phrase=phrase(new_text, "glared", new=("quill",)),
        phrase_position=position_at(1, new_text),
        key=key_at(1),
        fragment_score=0.5,
    )
    rule = SectionRule(UserKnowledge(EMPTY_VOCABULARY, CEFRLevel.B1, None), None)

    result = plan_rebuild(
        SOURCE, [untouched], [word()], [built("glare", analysed)], False, rule,
    )

    [update] = result.occ_to_update_text
    assert update.earned_section is CandidateSection.EXTRA


def test_include_open_never_changes_the_decision_phrase_nor_the_exported_one() -> None:
    decision = row(id=1, score=0.5, shown=SELECTION, is_decision=True, has_results=True)
    exported = row(id=2, score=0.5, exported=True, has_results=True)
    analysed = [built(
        "glare", occ(1, 0.1, text="She glared back."), occ(2, 0.1, text="She glared back."),
    )]

    result = plan(
        [decision, exported], [word(status=WordStatus.LEARN, count=2)], analysed,
        include_open=True,
    )

    assert result.is_empty


def test_include_open_moves_the_selection_off_a_generated_phrase() -> None:
    generated = row(id=1, line=1, score=0.5, shown=SELECTION, has_results=True)
    analysed = [built("glare", occ(1, 0.5), occ(2, 0.1))]

    kept = plan([generated], [word(count=2)], analysed)
    moved = plan([generated], [word(count=2)], analysed, include_open=True)

    assert kept.selection_changes == ()
    assert [(i.occurrence.key, i.shown) for i in kept.occ_to_insert] == [(key_at(2), False)]
    assert [c.clear_selection for c in moved.selection_changes] == [(1,)]
    assert [(i.occurrence.key, i.shown) for i in moved.occ_to_insert] == [(key_at(2), True)]
    assert moved.occ_to_delete == ()
    assert moved.counts.cards_new_phrase == 1


def test_a_user_shown_auto_phrase_keeps_its_mark_and_gets_no_twin() -> None:
    mine = row(id=1, line=1, score=0.5, shown=USER, replaces=True)

    result = plan([mine], [word()], [built("glare", occ(1, 0.1))])

    assert result.is_empty


def test_word_data_is_updated_when_the_analysis_changed_it() -> None:
    shown = row(id=1, score=0.5, shown=SELECTION)

    result = plan([shown], [word(zipf=3.0)], [built("glare", occ(1, 0.5), zipf=4.0)])

    [update] = result.words_to_update
    assert (update.word_id, update.data.zipf_frequency) == (1, 4.0)


def test_lemmas_match_without_case() -> None:
    shown = row(id=1, score=0.5, shown=SELECTION)

    result = plan([shown], [word(lemma="Glare")], [built("glare", occ(1, 0.5))])

    assert result.is_empty
    assert WordKey.of("Glare", is_phrasal_verb=False) == WordKey.of("glare", False)


def test_cards_without_generation_counts_shown_phrases_left_to_generate() -> None:
    generated = row(id=1, score=0.5, shown=SELECTION, has_results=True)

    result = plan([generated], [word()], [
        built("glare", occ(1, 0.5)), built("linger", occ(4, 0.5)),
    ])

    assert result.counts.cards_without_generation == 1


def test_a_stale_breakdown_is_rewritten_but_rounding_is_no_change() -> None:
    shown = row(id=1, score=0.5, shown=SELECTION)
    stored = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 0.6, CEFRLevel.C1: 0.4})
    stored_word = replace(word(), data=replace(word().data, cefr_breakdown=stored))
    rounded_only = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 0.600001, CEFRLevel.C1: 0.399999})
    stale = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 0.3, CEFRLevel.C1: 0.7})

    same = plan([shown], [stored_word], [
        replace(built("glare", occ(1, 0.5)), cefr_breakdown=rounded_only),
    ])
    changed = plan([shown], [stored_word], [
        replace(built("glare", occ(1, 0.5)), cefr_breakdown=stale),
    ])

    assert same.is_empty
    assert [u.data.cefr_breakdown for u in changed.words_to_update] == [stale]


# ── a key that moved within its line ─────────────────────────────────────────


def _at(line: int, char: int, *, text: str = TEXTS[0]) -> BuiltOccurrence:
    return replace(occ(line, text=text), key=OccurrenceKey(block=0, line=line, char=char))


@pytest.mark.parametrize("include_open", [False, True])
def test_a_phrase_whose_key_moved_within_its_line_is_found_again_by_its_text(
    include_open: bool,
) -> None:
    """A phrase keyed by another rule (an older analysis, a migrated card) is the
    occurrence on its line with the same text: it keeps its id and results."""
    stored = row(id=5, line=2, shown=SELECTION, has_results=True, text=TEXTS[0])
    moved = OccurrenceKey(block=0, line=2, char=4)

    result = plan([stored], [word()], [built("glare", _at(2, 4))], include_open=include_open)

    assert result.occ_to_delete == ()
    assert result.occ_to_insert == ()
    assert result.occ_to_rekey == (OccurrenceRekey(occurrence_id=5, key=moved),)


def test_a_phrase_with_another_text_on_its_line_is_not_that_occurrence() -> None:
    stored = row(id=5, line=2, shown=SELECTION, text=TEXTS[0])

    result = plan([stored], [word()], [built("glare", _at(2, 4, text=TEXTS[1]))])

    assert result.occ_to_rekey == ()
    assert result.occ_to_delete == (5,)
    assert [i.occurrence.key.char for i in result.occ_to_insert] == [4]


def test_a_moved_key_goes_to_the_nearest_free_occurrence_of_its_line() -> None:
    stored = [row(id=5, line=2, text=TEXTS[0], has_results=True), row(id=6, line=3)]

    result = plan(stored, [word()], [built("glare", _at(2, 9), _at(2, 3), occ(3))])

    assert result.occ_to_rekey == (
        OccurrenceRekey(occurrence_id=5, key=OccurrenceKey(block=0, line=2, char=3)),
    )
    assert [i.occurrence.key.char for i in result.occ_to_insert] == [9]


def test_a_moved_key_never_takes_an_occurrence_another_phrase_holds() -> None:
    stored = [
        row(id=5, line=2, text=TEXTS[0]),
        replace(row(id=6, line=2, text=TEXTS[0]), key=OccurrenceKey(block=0, line=2, char=4)),
    ]

    result = plan(stored, [word()], [built("glare", _at(2, 4))])

    assert result.occ_to_rekey == ()
    assert result.occ_to_delete == (5,)


@pytest.mark.parametrize("include_open", [False, True])
def test_after_a_moved_key_is_found_a_second_rebuild_changes_nothing(
    include_open: bool,
) -> None:
    store = Store(
        rows={5: row(id=5, line=2, shown=SELECTION, has_results=True)}, words={1: word()},
    )
    analysed = [built("glare", _at(2, 4))]
    store.apply(store.plan(analysed, include_open))

    assert store.plan(analysed, include_open).is_empty


def test_of_two_occurrences_on_its_line_a_moved_key_takes_the_one_of_its_own_target() -> None:
    """Same text, same line: the phrase whose target is the second "glared" is that
    occurrence, though the first is nearer."""
    text = "He glared and glared."
    first, second = (text_phrase(text).with_target((i,)) for i in (1, 3))
    position = position_at(2, text)
    stored = replace(
        row(id=5, line=2, text=text, has_results=True),
        phrase_hash=OccurrenceRow.hash_phrase(second, position),
    )
    analysed = [
        BuiltOccurrence(
            phrase=found, phrase_position=position,
            key=OccurrenceKey(block=0, line=2, char=char), fragment_score=0.5,
        )
        for found, char in ((first, 3), (second, 14))
    ]

    result = plan([stored], [word()], [built("glare", *analysed)])

    assert result.occ_to_rekey == (
        OccurrenceRekey(occurrence_id=5, key=OccurrenceKey(block=0, line=2, char=14)),
    )
    assert [i.occurrence.key.char for i in result.occ_to_insert] == [3]


# ── protection: the user's marks and work survive, with or without include_open ─

PROTECTED_ROWS = {
    "learn": (row(id=1, shown=SELECTION, choice=CardChoice.LEARN), WordStatus.LEARN),
    "cloze": (row(id=1, shown=SELECTION, choice=CardChoice.CLOZE), WordStatus.LEARN),
    "known": (row(id=1, shown=SELECTION, choice=CardChoice.KNOWN), WordStatus.KNOWN),
    "skip": (row(id=1, shown=SELECTION, choice=CardChoice.SKIP), WordStatus.NEW),
    "in anki": (
        row(id=1, shown=SELECTION, choice=CardChoice.LEARN, exported=True), WordStatus.LEARNING,
    ),
    "known in anki": (
        row(id=1, shown=SELECTION, choice=CardChoice.KNOWN, exported=True), WordStatus.KNOWN,
    ),
    "edited": (row(id=1, shown=SELECTION, edited=True), WordStatus.NEW),
    "picked by the user": (row(id=1, shown=USER), WordStatus.NEW),
    "manual": (row(id=1, origin=MANUAL, shown=USER), WordStatus.NEW),
    "example": (row(id=1, origin=EXAMPLE, shown=USER), WordStatus.NEW),
    "collected": (row(id=1, origin=COLLECTED, shown=USER), WordStatus.NEW),
}
CHANGED_TEXT = "He glared at me, again."


@pytest.mark.parametrize("include_open", [False, True])
@pytest.mark.parametrize("kind", PROTECTED_ROWS)
def test_a_protected_card_the_analysis_lost_stays_with_its_word(
    kind: str, include_open: bool,
) -> None:
    protected, status = PROTECTED_ROWS[kind]
    protected = replace(protected, has_results=True)

    result = plan([protected], [word(status=status)], [], include_open=include_open)

    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()


@pytest.mark.parametrize("include_open", [False, True])
@pytest.mark.parametrize("kind", PROTECTED_ROWS)
def test_a_protected_card_keeps_its_text_and_results(kind: str, include_open: bool) -> None:
    protected, status = PROTECTED_ROWS[kind]
    protected = replace(protected, has_results=True, has_active_job=True)

    result = plan(
        [protected], [word(status=status)],
        [built("glare", occ(1, 0.1, text=CHANGED_TEXT))], include_open=include_open,
    )

    assert (result.occ_to_update_text, result.occ_to_update_score, result.occ_to_delete) == (
        (), (), (),
    )
    assert result.counts.cards_text_reset == 0


@pytest.mark.parametrize("work", ["results", "job"])
def test_results_and_a_job_keep_a_lost_card_only_without_include_open(work: str) -> None:
    generated = row(id=1, shown=SELECTION, has_results=work == "results", has_job=work == "job")

    kept = plan([generated], [word()], [], include_open=False)
    rebuilt = plan([generated], [word()], [], include_open=True)

    assert (kept.occ_to_delete, kept.words_to_delete) == ((), ())
    assert (rebuilt.occ_to_delete, rebuilt.words_to_delete) == ((1,), (1,))


def test_the_cards_choice_decides_the_word_not_its_stored_status() -> None:
    learn = row(id=1, shown=SELECTION, choice=CardChoice.LEARN)
    open_card = row(id=2, candidate_id=2, shown=SELECTION)

    result = plan(
        [learn, open_card],
        [word(status=WordStatus.NEW), word(2, "linger", status=WordStatus.KNOWN)], [],
    )

    assert result.words_to_delete == (2,)
    assert result.occ_to_delete == (2,)

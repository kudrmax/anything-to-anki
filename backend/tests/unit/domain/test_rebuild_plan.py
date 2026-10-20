"""The rebuild plan: what a re-analysis changes in the words and phrases of a source,
and that it never loses the user's work."""
from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

import pytest
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.services.candidate_sections import SectionRule
from backend.domain.services.phrase_protection import is_untouchable
from backend.domain.services.phrase_selection import SelectionScore, is_frozen, select_phrases
from backend.domain.services.rebuild_plan import (
    OccurrenceRekey,
    RebuildCounts,
    RebuildPlan,
    RebuildRules,
    SectionChange,
    plan_rebuild,
)
from backend.domain.value_objects.built_analysis import BuiltOccurrence, BuiltWord, WordKey
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
from backend.domain.value_objects.occurrence_row import OccurrenceRow
from backend.domain.value_objects.phrase_generation import NO_GENERATION, PhraseGeneration
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.rebuild_mode import RebuildMode
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
    MEANING,
    READY_RULE,
    SELECTION,
    TTS,
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
SCORES = (10.0, 20.0, 50.0, None)
UPDATE = RebuildMode.UPDATE
RECUT = RebuildMode.RECUT
MODES = (UPDATE, RECUT)
SCORE = SelectionScore(knowledge=None, weight_unknown=1)
POLISHED = PhraseGeneration(polish=True)
KEY_LINES = 5


def _decided(w: WordRow) -> bool:
    """The stored status, as the oracle for what the plan derives from the cards."""
    return w.status is not WordStatus.NEW


def rules(
    mode: RebuildMode = UPDATE,
    sections: SectionRule = READY_RULE,
    done_on_the_fly: frozenset[WordKey] = frozenset(),
) -> RebuildRules:
    return RebuildRules(
        mode=mode, sections=sections, score=SCORE, done_on_the_fly=done_on_the_fly,
    )


def plan(
    existing: list[OccurrenceRow],
    words: list[WordRow],
    analysed: list[BuiltWord],
    *,
    mode: RebuildMode = UPDATE,
    done_on_the_fly: frozenset[WordKey] = frozenset(),
) -> RebuildPlan:
    return plan_rebuild(
        SOURCE, existing, words, analysed, rules(mode, done_on_the_fly=done_on_the_fly),
    )


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
            drop = text_update.drop_text_generation
            self.rows[old.id] = replace(
                old,
                text_hash=OccurrenceRow.hash_text(text_update.phrase.text),
                phrase_hash=OccurrenceRow.hash_phrase(
                    text_update.phrase, text_update.phrase_position,
                ),
                fragment_score=text_update.fragment_score,
                revision=old.revision + (1 if text_update.bump_revision else 0),
                generation=replace(old.generation, polish=False, text_media=False)
                if drop else old.generation,
                shows_polish=False if drop else old.shows_polish,
                earned_section=text_update.earned_section,
                source_phrase=text_update.phrase,
                shown_phrase=old.shown_phrase if old.shows_polish and not drop
                else text_update.phrase,
            )
        for section_change in plan.section_changes:
            self.rows[section_change.occurrence_id] = replace(
                self.rows[section_change.occurrence_id],
                earned_section=section_change.earned_section,
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
                generation=NO_GENERATION, binding=None, has_active_job=False,
                text_hash=OccurrenceRow.hash_text(o.phrase.text),
                fragment_score=o.fragment_score, shows_polish=False, replaces_selection=False,
                phrase_hash=OccurrenceRow.hash_phrase(o.phrase, o.phrase_position),
                source_phrase=o.phrase, shown_phrase=o.phrase,
                earned_section=insert.earned_section,
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

    def plan(self, analysed: list[BuiltWord], mode: RebuildMode) -> RebuildPlan:
        return plan_rebuild(
            SOURCE, list(self.rows.values()), list(self.words.values()), analysed, rules(mode),
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
        generation=rnd.choice([NO_GENERATION] * 3 + [MEANING, TTS]),
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
            occ(line, rnd.choice((10.0, 20.0, 50.0)), text=rnd.choice(TEXTS),
                variant=rnd.random() < 0.3)
            for line in sorted(lines)
        ), zipf=rnd.choice((3.0, 4.0))))
    return rows, words, analysed


CASES = [(seed, mode) for seed in range(GENERATED_CASES) for mode in MODES]


@pytest.mark.parametrize(("seed", "mode"), CASES)
def test_rebuilding_twice_gives_an_empty_plan(seed: int, mode: RebuildMode) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})

    store.apply(store.plan(analysed, mode))

    again = store.plan(analysed, mode)
    assert again.is_empty
    assert not again.section_changes


@pytest.mark.parametrize(("seed", "mode"), CASES)
def test_untouchable_phrases_are_never_deleted_nor_changed(seed: int, mode: RebuildMode) -> None:
    rows, words, analysed = random_source(seed)
    untouchable = {r.id for r in rows if is_untouchable(r)}

    result = plan_rebuild(SOURCE, rows, words, analysed, rules(mode))

    changed = (
        set(result.occ_to_delete)
        | {u.occurrence_id for u in result.occ_to_update_text}
        | {u.occurrence_id for u in result.occ_to_update_score}
    )
    assert not changed & untouchable
    words_of_untouchable = {r.candidate_id for r in rows if r.id in untouchable}
    assert not set(result.words_to_delete) & words_of_untouchable


@pytest.mark.parametrize("seed", range(GENERATED_CASES))
def test_an_update_changes_no_text_and_drops_nothing_of_a_word_still_found(seed: int) -> None:
    rows, words, analysed = random_source(seed)
    found = {b.key for b in analysed}
    word_found = {w.id: w.key in found for w in words}
    by_id = {r.id: r for r in rows}

    result = plan_rebuild(SOURCE, rows, words, analysed, rules(UPDATE))

    for update in result.occ_to_update_text:
        old = by_id[update.occurrence_id]
        assert OccurrenceRow.hash_text(update.phrase.text) == old.text_hash
        assert not update.bump_revision
        assert not update.drop_text_generation
    for deleted in result.occ_to_delete:
        old = by_id[deleted]
        if word_found[old.candidate_id]:
            assert not old.generation.any
            assert not old.has_active_job


@pytest.mark.parametrize("seed", range(GENERATED_CASES))
def test_a_recut_drops_only_what_was_made_of_the_old_text(seed: int) -> None:
    rows, words, analysed = random_source(seed)
    by_id = {r.id: r for r in rows}

    result = plan_rebuild(SOURCE, rows, words, analysed, rules(RECUT))

    for update in result.occ_to_update_text:
        old = by_id[update.occurrence_id]
        new_text = OccurrenceRow.hash_text(update.phrase.text) != old.text_hash
        assert update.bump_revision == new_text
        assert update.drop_text_generation == (new_text and old.generation.of_text)


@pytest.mark.parametrize(("seed", "mode"), CASES)
def test_decided_words_are_never_removed(seed: int, mode: RebuildMode) -> None:
    rows, words, analysed = random_source(seed)

    result = plan_rebuild(SOURCE, rows, words, analysed, rules(mode))

    assert not set(result.words_to_delete) & {w.id for w in words if _decided(w)}


@pytest.mark.parametrize(("seed", "mode"), CASES)
def test_after_a_rebuild_selection_holds_its_invariant(seed: int, mode: RebuildMode) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})
    before = dict(store.rows)

    store.apply(store.plan(analysed, mode))

    for kept_id, kept in store.rows.items():
        if kept_id in before and before[kept_id].shown_by is USER:
            assert kept.shown_by is USER
    for w in store.words.values():
        mine = [r for r in store.rows.values() if r.candidate_id == w.id]
        assert select_phrases(mine, _decided(w), SCORE).is_empty
        if _decided(w):
            continue
        selected = [r for r in mine if r.shown_by is SELECTION]
        loose = [r for r in selected if not is_frozen(r)]
        assert all(r.origin is AUTO for r in selected)
        assert len(loose) <= 1
        assert not loose or len(selected) == 1


@pytest.mark.parametrize(("seed", "mode"), CASES)
def test_words_without_phrases_and_decision_go(seed: int, mode: RebuildMode) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})

    store.apply(store.plan(analysed, mode))

    for w in store.words.values():
        assert _decided(w) or any(r.candidate_id == w.id for r in store.rows.values())


@pytest.mark.parametrize(("seed", "mode"), CASES)
def test_no_place_holds_two_auto_phrases_of_a_word(seed: int, mode: RebuildMode) -> None:
    rows, words, analysed = random_source(seed)
    store = Store({r.id: r for r in rows}, {w.id: w for w in words})

    store.apply(store.plan(analysed, mode))

    keys = [
        (r.candidate_id, r.key) for r in store.rows.values()
        if r.origin is AUTO and r.key is not None
    ]
    assert len(keys) == len(set(keys))


# ── the rules one by one ────────────────────────────────────────────────────


def test_a_new_word_is_created_with_its_best_phrase_shown() -> None:
    result = plan([], [], [built("glare", occ(0, 50.0), occ(1, 10.0))])

    assert [w.lemma for w in result.words_to_create] == ["glare"]
    assert [(i.occurrence.key, i.shown) for i in result.occ_to_insert] == [
        (key_at(0), False), (key_at(1), True),
    ]
    assert result.counts.words_added == 1


def test_a_manual_phrase_blocks_a_later_auto_phrase_at_its_place() -> None:
    manual = row(id=1, line=2, origin=MANUAL, shown=USER)

    result = plan([manual], [word()], [built("glare", occ(2, 10.0))])

    assert result.occ_to_insert == ()
    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()


def test_auto_phrases_match_by_key_and_keep_their_ids() -> None:
    old = row(id=5, line=3, score=50.0, shown=SELECTION)

    result = plan([old], [word()], [built("glare", occ(3, 20.0))])

    assert result.occ_to_insert == ()
    assert [u.occurrence_id for u in result.occ_to_update_score] == [5]
    assert result.occ_to_update_score[0].fragment_score == 20.0


@pytest.mark.parametrize("mode", MODES)
def test_a_decided_word_keeps_every_phrase_though_the_analysis_has_lost_it(
    mode: RebuildMode,
) -> None:
    decision = row(id=1, shown=SELECTION, is_decision=True)
    hidden = row(id=2)

    result = plan([decision, hidden], [word(status=WordStatus.LEARN)], [], mode=mode)

    assert result.words_to_delete == ()
    assert result.occ_to_delete == ()


def test_an_untouched_word_the_analysis_lost_goes_with_its_phrases() -> None:
    shown = row(id=1, shown=SELECTION)

    result = plan([shown], [word()], [])

    assert result.words_to_delete == (1,)
    assert result.occ_to_delete == (1,)
    assert result.counts.words_removed == 1


@pytest.mark.parametrize("mode", MODES)
def test_a_word_the_analysis_lost_goes_with_whatever_was_made_for_its_card(
    mode: RebuildMode,
) -> None:
    generated = row(id=1, shown=SELECTION, generation=MEANING, has_job=True)

    result = plan([generated], [word()], [], mode=mode)

    assert (result.occ_to_delete, result.words_to_delete) == ((1,), (1,))
    assert result.counts == RebuildCounts(words_removed=1, cards_lost_generation=1)


def test_a_hidden_phrase_of_a_lost_word_is_no_lost_card() -> None:
    hidden = row(id=2, generation=MEANING)
    shown = row(id=1, shown=SELECTION)

    result = plan([shown, hidden], [word()], [])

    assert result.counts.cards_lost_generation == 0


def test_a_word_done_on_the_fly_keeps_every_phrase_though_the_analysis_lost_it() -> None:
    shown = row(id=1, shown=SELECTION, generation=MEANING, section=EXTRA)
    hidden = row(id=2)
    done = frozenset({word().key})

    result = plan([shown, hidden], [word()], [], done_on_the_fly=done)

    assert (result.occ_to_delete, result.words_to_delete) == ((), ())
    assert result.section_changes == (SectionChange(1, READY),)


@pytest.mark.parametrize("mode", MODES)
def test_a_skipped_phrase_the_analysis_lost_stays_with_its_word(mode: RebuildMode) -> None:
    skipped = row(id=1, shown=SELECTION, skipped=True, generation=MEANING)

    result = plan([skipped], [word()], [], mode=mode)

    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()
    assert result.is_empty


def test_a_recut_keeps_the_text_of_a_skipped_phrase() -> None:
    skipped = row(id=1, score=50.0, shown=SELECTION, skipped=True, generation=MEANING)
    analysed = [built("glare", occ(1, 50.0, text="She glared back."))]

    result = plan([skipped], [word()], analysed, mode=RECUT)

    assert result.occ_to_update_text == ()
    assert result.occ_to_delete == ()
    assert result.counts.cards_recut == 0


@pytest.mark.parametrize("mode", MODES)
def test_a_polished_phrase_keeps_its_words(mode: RebuildMode) -> None:
    polished = row(id=1, score=50.0, shown=SELECTION, shows_polish=True)

    result = plan([polished], [word()], [built("glare", occ(1, 30.0, variant=True))], mode=mode)

    assert result.occ_to_update_text == ()
    assert [u.occurrence_id for u in result.occ_to_update_score] == [1]


@pytest.mark.parametrize("mode", MODES)
def test_a_phrase_with_the_same_text_gets_its_new_words_keeping_what_was_made(
    mode: RebuildMode,
) -> None:
    generated = row(id=1, score=50.0, shown=SELECTION, generation=MEANING)

    result = plan([generated], [word()], [built("glare", occ(1, 50.0, variant=True))], mode=mode)

    [update] = result.occ_to_update_text
    assert (update.occurrence_id, update.bump_revision, update.drop_text_generation) == (
        1, False, False,
    )


@pytest.mark.parametrize("generation", [NO_GENERATION, MEANING, TTS, POLISHED])
def test_an_update_never_cuts_a_phrase_again(generation: PhraseGeneration) -> None:
    stored = row(id=1, score=50.0, shown=SELECTION, generation=generation)
    analysed = [built("glare", occ(1, 50.0, text="She glared back."))]

    assert plan([stored], [word()], analysed).is_empty


def test_a_recut_cuts_a_phrase_again_keeping_its_meaning() -> None:
    generated = row(id=1, score=50.0, shown=SELECTION, generation=MEANING)
    analysed = [built("glare", occ(1, 50.0, text="She glared back."))]

    result = plan([generated], [word()], analysed, mode=RECUT)

    [update] = result.occ_to_update_text
    assert update.phrase == text_phrase("She glared back.")
    assert update.phrase_position == position_at(1, "She glared back.")
    assert (update.bump_revision, update.drop_text_generation) == (True, False)
    assert result.counts == RebuildCounts(cards_recut=1)


@pytest.mark.parametrize("generation", [
    TTS, POLISHED, PhraseGeneration(polish=True, meaning=True),
], ids=["tts", "polish", "polish and meaning"])
def test_a_recut_drops_what_was_made_of_the_old_text(generation: PhraseGeneration) -> None:
    stored = row(id=1, score=50.0, shown=SELECTION, generation=generation)
    analysed = [built("glare", occ(1, 50.0, text="She glared back."))]

    result = plan([stored], [word()], analysed, mode=RECUT)

    [update] = result.occ_to_update_text
    assert (update.bump_revision, update.drop_text_generation) == (True, True)
    assert result.counts == RebuildCounts(cards_recut=1, cards_recut_lost_text_generation=1)


def test_a_recut_phrase_carries_the_section_of_its_new_text() -> None:
    untouched = row(id=1, score=50.0, shown=SELECTION)
    new_text = "She glared quill"
    analysed = BuiltOccurrence(
        phrase=phrase(new_text, "glared", new=("quill",)),
        phrase_position=position_at(1, new_text),
        key=key_at(1),
        fragment_score=50.0,
    )
    rule = SectionRule(UserKnowledge(EMPTY_VOCABULARY, CEFRLevel.B1, None), None)

    result = plan_rebuild(
        SOURCE, [untouched], [word()], [built("glare", analysed)], rules(RECUT, rule),
    )

    [update] = result.occ_to_update_text
    assert update.earned_section is CandidateSection.EXTRA


@pytest.mark.parametrize("mode", MODES)
def test_the_decision_phrase_and_the_exported_one_never_change(mode: RebuildMode) -> None:
    decision = row(id=1, score=50.0, shown=SELECTION, is_decision=True, generation=MEANING)
    exported = row(id=2, score=50.0, exported=True, generation=MEANING)
    analysed = [built(
        "glare", occ(1, 10.0, text="She glared back."), occ(2, 10.0, text="She glared back."),
    )]

    result = plan(
        [decision, exported], [word(status=WordStatus.LEARN, count=2)], analysed, mode=mode,
    )

    assert result.is_empty


@pytest.mark.parametrize("mode", MODES)
def test_the_card_moves_to_a_better_phrase_and_the_old_one_keeps_what_was_made(
    mode: RebuildMode,
) -> None:
    generated = row(id=1, line=1, score=50.0, shown=SELECTION, generation=MEANING)
    analysed = [built("glare", occ(1, 50.0), occ(2, 10.0))]

    moved = plan([generated], [word(count=2)], analysed, mode=mode)

    assert [c.clear_selection for c in moved.selection_changes] == [(1,)]
    assert [(i.occurrence.key, i.shown) for i in moved.occ_to_insert] == [(key_at(2), True)]
    assert moved.occ_to_delete == ()
    assert moved.counts.cards_moved == 1


def test_a_card_something_is_being_made_for_keeps_its_phrase() -> None:
    working = row(id=1, line=1, score=50.0, shown=SELECTION, has_job=True)
    analysed = [built("glare", occ(1, 50.0), occ(2, 10.0))]

    result = plan([working], [word(count=2)], analysed)

    assert result.selection_changes == ()
    assert [(i.occurrence.key, i.shown) for i in result.occ_to_insert] == [(key_at(2), False)]
    assert result.counts.cards_moved == 0


def test_a_user_shown_auto_phrase_keeps_its_mark_and_gets_no_twin() -> None:
    mine = row(id=1, line=1, score=50.0, shown=USER, replaces=True)

    result = plan([mine], [word()], [built("glare", occ(1, 10.0))])

    assert result.is_empty


def test_word_data_is_updated_when_the_analysis_changed_it() -> None:
    shown = row(id=1, score=50.0, shown=SELECTION)

    result = plan([shown], [word(zipf=3.0)], [built("glare", occ(1, 50.0), zipf=4.0)])

    [update] = result.words_to_update
    assert (update.word_id, update.data.zipf_frequency) == (1, 4.0)


def test_lemmas_match_without_case() -> None:
    shown = row(id=1, score=50.0, shown=SELECTION)

    result = plan([shown], [word(lemma="Glare")], [built("glare", occ(1, 50.0))])

    assert result.is_empty
    assert WordKey.of("Glare", is_phrasal_verb=False) == WordKey.of("glare", False)


def test_a_stale_breakdown_is_rewritten_but_rounding_is_no_change() -> None:
    shown = row(id=1, score=50.0, shown=SELECTION)
    stored = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 0.6, CEFRLevel.C1: 0.4})
    stored_word = replace(word(), data=replace(word().data, cefr_breakdown=stored))
    rounded_only = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 0.600001, CEFRLevel.C1: 0.399999})
    stale = breakdown(CEFRLevel.B2, {CEFRLevel.B2: 0.3, CEFRLevel.C1: 0.7})

    same = plan([shown], [stored_word], [
        replace(built("glare", occ(1, 50.0)), cefr_breakdown=rounded_only),
    ])
    changed = plan([shown], [stored_word], [
        replace(built("glare", occ(1, 50.0)), cefr_breakdown=stale),
    ])

    assert same.is_empty
    assert [u.data.cefr_breakdown for u in changed.words_to_update] == [stale]


# ── a key that moved within its line ─────────────────────────────────────────


def _at(line: int, char: int, *, text: str = TEXTS[0]) -> BuiltOccurrence:
    return replace(occ(line, text=text), key=OccurrenceKey(block=0, line=line, char=char))


@pytest.mark.parametrize("mode", MODES)
def test_a_phrase_whose_key_moved_within_its_line_is_found_again_by_its_text(
    mode: RebuildMode,
) -> None:
    """A phrase keyed by another rule (an older analysis, a migrated card) is the
    occurrence on its line with the same text: it keeps its id and results."""
    stored = row(id=5, line=2, shown=SELECTION, generation=MEANING, text=TEXTS[0])
    moved = OccurrenceKey(block=0, line=2, char=4)

    result = plan([stored], [word()], [built("glare", _at(2, 4))], mode=mode)

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
    stored = [row(id=5, line=2, text=TEXTS[0], generation=MEANING), row(id=6, line=3)]

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


@pytest.mark.parametrize("mode", MODES)
def test_after_a_moved_key_is_found_a_second_rebuild_changes_nothing(mode: RebuildMode) -> None:
    store = Store(
        rows={5: row(id=5, line=2, shown=SELECTION, generation=MEANING)}, words={1: word()},
    )
    analysed = [built("glare", _at(2, 4))]
    store.apply(store.plan(analysed, mode))

    assert store.plan(analysed, mode).is_empty


def test_of_two_occurrences_on_its_line_a_moved_key_takes_the_one_of_its_own_target() -> None:
    """Same text, same line: the phrase whose target is the second "glared" is that
    occurrence, though the first is nearer."""
    text = "He glared and glared."
    first, second = (text_phrase(text).with_target((i,)) for i in (1, 3))
    position = position_at(2, text)
    stored = replace(
        row(id=5, line=2, text=text, generation=MEANING),
        phrase_hash=OccurrenceRow.hash_phrase(second, position),
    )
    analysed = [
        BuiltOccurrence(
            phrase=found, phrase_position=position,
            key=OccurrenceKey(block=0, line=2, char=char), fragment_score=50.0,
        )
        for found, char in ((first, 3), (second, 14))
    ]

    result = plan([stored], [word()], [built("glare", *analysed)])

    assert result.occ_to_rekey == (
        OccurrenceRekey(occurrence_id=5, key=OccurrenceKey(block=0, line=2, char=14)),
    )
    assert [i.occurrence.key.char for i in result.occ_to_insert] == [3]


# ── protection: the user's marks and work survive an update and a recut ──────

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


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", PROTECTED_ROWS)
def test_a_protected_card_the_analysis_lost_stays_with_its_word(
    kind: str, mode: RebuildMode,
) -> None:
    protected, status = PROTECTED_ROWS[kind]
    protected = replace(protected, generation=MEANING)

    result = plan([protected], [word(status=status)], [], mode=mode)

    assert result.occ_to_delete == ()
    assert result.words_to_delete == ()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", PROTECTED_ROWS)
def test_a_protected_card_keeps_its_text_and_results(kind: str, mode: RebuildMode) -> None:
    protected, status = PROTECTED_ROWS[kind]
    protected = replace(protected, generation=MEANING, has_active_job=True)

    result = plan(
        [protected], [word(status=status)],
        [built("glare", occ(1, 10.0, text=CHANGED_TEXT))], mode=mode,
    )

    assert (result.occ_to_update_text, result.occ_to_update_score, result.occ_to_delete) == (
        (), (), (),
    )
    assert result.counts.cards_recut == 0


@pytest.mark.parametrize("work", ["generation", "job"])
def test_a_phrase_whose_place_is_gone_stays_in_an_update_if_something_is_made_for_it(
    work: str,
) -> None:
    gone = row(
        id=1, line=1, shown=SELECTION,
        generation=MEANING if work == "generation" else NO_GENERATION, has_job=work == "job",
    )
    analysed = [built("glare", occ(3, 50.0))]

    kept = plan([gone], [word()], analysed)
    recut = plan([gone], [word()], analysed, mode=RECUT)

    assert kept.occ_to_delete == ()
    assert recut.occ_to_delete == (1,)
    assert recut.counts.cards_lost_generation == (1 if work == "generation" else 0)


def test_a_phrase_whose_place_is_gone_goes_in_an_update_when_nothing_is_made_for_it() -> None:
    gone = row(id=1, line=1, shown=SELECTION)

    result = plan([gone], [word()], [built("glare", occ(3, 50.0))])

    assert result.occ_to_delete == (1,)
    assert [(i.occurrence.key, i.shown) for i in result.occ_to_insert] == [(key_at(3), True)]


def test_a_kept_phrase_whose_place_is_gone_keeps_its_line_free_of_a_twin() -> None:
    """Its key moved with its text, so it is not found again: the analysis's occurrence on
    its line is that place, and gets no second phrase."""
    gone = row(id=1, line=2, shown=SELECTION, generation=MEANING, text=TEXTS[0])
    analysed = [built("glare", _at(2, 4, text=TEXTS[1]))]

    result = plan([gone], [word()], analysed)

    assert result.occ_to_insert == ()
    assert result.occ_to_delete == ()


def test_the_cards_choice_decides_the_word_not_its_stored_status() -> None:
    learn = row(id=1, shown=SELECTION, choice=CardChoice.LEARN)
    open_card = row(id=2, candidate_id=2, shown=SELECTION)

    result = plan(
        [learn, open_card],
        [word(status=WordStatus.NEW), word(2, "linger", status=WordStatus.KNOWN)], [],
    )

    assert result.words_to_delete == (2,)
    assert result.occ_to_delete == (2,)


# ── sections are re-stamped ───────────────────────────────────────────────────

EXTRA = CandidateSection.EXTRA
READY = CandidateSection.READY


def test_rebuild_restamps_an_open_phrase_whose_section_changed() -> None:
    stale = row(id=1, shown=SELECTION, section=EXTRA)

    result = plan([stale], [word()], [built("glare", occ(1))])

    assert result.section_changes == (SectionChange(1, READY),)


def test_rebuild_restamps_manual_and_example_phrases() -> None:
    rows = [
        row(id=1, origin=MANUAL, shown=USER, section=EXTRA),
        row(id=2, origin=EXAMPLE, shown=USER, section=EXTRA),
    ]

    result = plan(rows, [word()], [])

    assert result.section_changes == (SectionChange(1, READY), SectionChange(2, READY))


@pytest.mark.parametrize("kept", [
    row(id=1, shown=USER, skipped=True, section=EXTRA),
    row(id=1, shown=USER, is_decision=True, section=EXTRA),
    row(id=1, shown=USER, exported=True, section=EXTRA),
], ids=["skipped", "decision", "exported"])
def test_rebuild_keeps_the_section_of_a_chosen_or_exported_phrase(kept: OccurrenceRow) -> None:
    result = plan([kept], [word()], [built("glare", occ(1))])

    assert not result.section_changes


def test_a_rebuild_that_only_moves_sections_is_not_empty() -> None:
    stale = row(id=1, shown=SELECTION, generation=MEANING, section=EXTRA)

    result = plan([stale], [word()], [built("glare", occ(1))])

    assert not result.is_empty
    assert result.counts == RebuildCounts()


def test_restamping_uses_the_updated_word_data() -> None:
    open_phrase = row(id=1, shown=SELECTION)
    rule = SectionRule(knowledge=None, frequent_threshold=FrequentWordThreshold("x", 5.0, ()))

    result = plan_rebuild(
        SOURCE, [open_phrase], [word(zipf=3.0)], [built("glare", occ(1), zipf=6.0)],
        rules(sections=rule),
    )

    assert result.section_changes == (SectionChange(1, CandidateSection.PROBABLY_KNOWN),)

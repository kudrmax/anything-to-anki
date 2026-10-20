from backend.domain.value_objects.card_change import (
    BindingChanged,
    DecisionChanged,
    LevelChanged,
    MarkChanged,
    PhraseChanged,
    SourceDeleted,
    WordsChanged,
)


def test_single_lemma_events_lower_case_it() -> None:
    assert DecisionChanged("Run").lemma == "run"
    assert MarkChanged("GIVE In").lemma == "give in"
    assert BindingChanged("Make A Decision").lemma == "make a decision"


def test_set_events_lower_case_every_member() -> None:
    assert WordsChanged(1, frozenset({"Run", "JUMP"})).lemmas == frozenset({"run", "jump"})
    assert SourceDeleted(1, frozenset({"Run", "run"})).lemmas == frozenset({"run"})


def test_equal_events_are_one_in_a_set() -> None:
    events = {DecisionChanged("Run"), DecisionChanged("run"), PhraseChanged(1), PhraseChanged(1)}

    assert events == {DecisionChanged("run"), PhraseChanged(1)}


def test_level_changed_events_are_equal() -> None:
    assert LevelChanged() == LevelChanged()
    assert hash(LevelChanged()) == hash(LevelChanged())

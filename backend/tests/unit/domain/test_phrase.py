from __future__ import annotations

import pytest
from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.services.phrase_building import (
    TokenFacts,
    build_phrase,
    target_by_lemma,
    word_spans,
    words_of,
)
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Phrase, Word

pytestmark = pytest.mark.unit


def _tokens(text: str, lemmas: dict[str, str] | None = None) -> list[TokenFacts]:
    """One token per whitespace piece's letters, like a simple tokenizer would give."""
    lemmas = lemmas or {}
    facts: list[TokenFacts] = []
    for start, end in word_spans(text):
        word = text[start:end]
        facts.append(TokenFacts(
            start=start, end=end, lemma=lemmas.get(word, word.lower()), level=CEFRLevel.B1,
            zipf=4.0, content=True, alpha=True,
        ))
    return facts


def _word(start: int, end: int, lemma: str = "w") -> Word:
    return Word(start=start, end=end, lemma=lemma, level=CEFRLevel.B1, zipf=4.0, content=True)


class TestWordSpans:
    def test_punctuation_stays_outside_words(self) -> None:
        text = "“Hello,” she said — don't stop; well-known."
        assert [text[s:e] for s, e in word_spans(text)] == [
            "Hello", "she", "said", "don't", "stop", "well-known",
        ]

    def test_line_breaks_split_words(self) -> None:
        text = "Hello darkness\nmy old friend"
        assert [text[s:e] for s, e in word_spans(text)] == [
            "Hello", "darkness", "my", "old", "friend",
        ]


class TestBuildPhrase:
    def test_target_is_the_words_its_spans_touch(self) -> None:
        text = "A sudden gale scattered the gulls."
        phrase = build_phrase(text, _tokens(text), [(14, 23)])
        assert phrase.target == (3,)
        assert phrase.target_text() == "scattered"

    def test_separated_phrasal_verb_is_two_words(self) -> None:
        text = "She gave it up."
        phrase = build_phrase(text, _tokens(text), [(4, 8), (12, 14)])
        assert phrase.target == (1, 3)
        assert phrase.target_text() == "gave up"
        assert [phrase.word_text(i) for i, _ in enumerate(phrase.words)] == [
            "She", "gave", "it", "up",
        ]

    def test_target_outside_the_words_is_an_error(self) -> None:
        text = "Nothing here."
        with pytest.raises(TargetNotInPhraseError):
            build_phrase(text, _tokens(text), [(12, 13)])

    def test_word_of_several_tokens_takes_its_own_text_as_lemma(self) -> None:
        text = "don't"
        tokens = [
            TokenFacts(0, 2, "do", CEFRLevel.A1, 6.0, False, True),
            TokenFacts(2, 5, "not", CEFRLevel.A1, 6.5, False, False),
        ]
        word = words_of(text, tokens)[0]
        assert (word.lemma, word.level, word.zipf, word.content) == (
            "don't", CEFRLevel.UNKNOWN, 6.5, False,
        )

    def test_word_of_one_token_takes_its_facts(self) -> None:
        text = "gulls"
        tokens = [TokenFacts(0, 5, "gull", CEFRLevel.C1, 2.9, True, True)]
        word = words_of(text, tokens)[0]
        assert (word.lemma, word.level, word.zipf, word.content) == (
            "gull", CEFRLevel.C1, 2.9, True,
        )


class TestTargetByLemma:
    def test_finds_an_inflected_form(self) -> None:
        text = "The wind scatters leaves."
        words = words_of(text, _tokens(text, {"scatters": "scatter"}))
        assert target_by_lemma(words, text, "scatter") == (2,)

    def test_finds_a_separated_phrasal_verb(self) -> None:
        text = "She gave it up at last."
        words = words_of(text, _tokens(text, {"gave": "give"}))
        assert target_by_lemma(words, text, "give up") == (1, 3)

    def test_missing_target_gives_nothing(self) -> None:
        text = "Nothing to see."
        words = words_of(text, _tokens(text))
        assert target_by_lemma(words, text, "scatter") == ()

    def test_matches_the_word_as_written_too(self) -> None:
        text = "The pants are blue."
        words = words_of(text, _tokens(text, {"pants": "pant"}))
        assert target_by_lemma(words, text, "pants") == (1,)


class TestPhraseInvariants:
    def test_rejects_an_empty_target(self) -> None:
        with pytest.raises(ValueError, match="target"):
            Phrase(text="Hi there", words=(_word(0, 2), _word(3, 8)), target=())

    def test_rejects_a_word_outside_the_text(self) -> None:
        with pytest.raises(ValueError, match="text"):
            Phrase(text="Hi", words=(_word(0, 5),), target=(0,))

    def test_rejects_overlapping_words(self) -> None:
        with pytest.raises(ValueError, match="order"):
            Phrase(text="Hello", words=(_word(0, 3), _word(2, 5)), target=(0,))

    def test_other_words_skip_the_target(self) -> None:
        phrase = Phrase(text="a b c", words=(_word(0, 1), _word(2, 3), _word(4, 5)), target=(1,))
        assert phrase.other_words() == (_word(0, 1), _word(4, 5))

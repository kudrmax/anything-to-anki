from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.utils.phrase_reader import PhraseReader
from backend.domain.entities.token_data import TokenData
from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.ports.text_analyzer import TextAnalyzer
from backend.domain.services.long_operation_progress import PartReport, no_report
from backend.domain.value_objects.cefr_level import CEFRLevel

pytestmark = pytest.mark.unit

STOP_WORDS = {"the", "a", "she", "it", "up"}


class _Analyzer(TextAnalyzer):
    """Splits by spaces and strips a final dot; lemmas come from the table."""

    def __init__(self, lemmas: dict[str, str]) -> None:
        self._lemmas = lemmas

    def analyze(self, text: str, report: PartReport = no_report) -> list[TokenData]:
        tokens: list[TokenData] = []
        offset = 0
        for i, piece in enumerate(text.split(" ")):
            word = piece.rstrip(".")
            tokens.append(TokenData(
                index=i, text=word, lemma=self._lemmas.get(word, word), pos="NOUN", tag="NN",
                head_index=i, children_indices=(), is_punct=False,
                is_stop=word.lower() in STOP_WORDS, is_alpha=word.isalpha(), is_propn=False,
                sent_index=0, char_start=offset,
            ))
            offset += len(piece) + 1
        return tokens


def _reader(lemmas: dict[str, str]) -> PhraseReader:
    cefr = MagicMock()
    cefr.classify.return_value = CEFRLevel.C1
    frequency = MagicMock()
    frequency.get_zipf_value.return_value = 3.0
    return PhraseReader(_Analyzer(lemmas), cefr, frequency)


class TestPhraseReader:
    def test_reads_the_target_from_the_given_characters(self) -> None:
        phrase = _reader({}).read("A sudden gale scattered the gulls.", [(14, 23)])
        assert phrase.target_text() == "scattered"
        assert phrase.words[3].level is CEFRLevel.C1

    def test_finds_the_target_in_a_new_text_by_its_dictionary_form(self) -> None:
        phrase = _reader({"scatters": "scatter"}).read_for("The wind scatters leaves.", "scatter")
        assert phrase.target_text() == "scatters"

    def test_picked_word_is_the_target_where_it_was_picked(self) -> None:
        phrase = _reader({}).read_picked("She runs fast she runs more.", [4])
        assert phrase.target == (4,)

    def test_picking_no_word_or_a_missing_one_is_refused(self) -> None:
        for picked in ([], [9]):
            with pytest.raises(TargetNotInPhraseError):
                _reader({}).read_picked("She runs fast.", picked)

    def test_new_text_without_the_target_is_refused(self) -> None:
        with pytest.raises(TargetNotInPhraseError):
            _reader({}).read_for("The wind blew the leaves away.", "scatter")

    def test_function_words_cannot_be_new(self) -> None:
        phrase = _reader({}).read("She gave it up.", [(4, 8)])
        assert [w.content for w in phrase.words] == [False, True, False, False]

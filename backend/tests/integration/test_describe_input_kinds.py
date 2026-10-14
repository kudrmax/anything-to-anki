"""Одна английская строка на экране Add: фраза, тема или источник — на настоящем spaCy."""

from __future__ import annotations

import pytest
from backend.application.use_cases.describe_input import DescribeInputUseCase
from backend.domain.ports.file_reader import FileReader
from backend.domain.services.input_kind_classifier import InputKindClassifier
from backend.domain.value_objects.input_kind import InputKind
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer

from tests.unit.infrastructure.readers.fakes import FakeYouTube

pytestmark = pytest.mark.integration


class NoFiles(FileReader):
    def exists(self, path: str) -> bool:
        return False

    def read_text(self, path: str) -> str:
        raise AssertionError("describing input never reads a file")


@pytest.fixture(scope="module")
def describe_kind():  # noqa: ANN201 — фабрика для параметризованных тестов
    use_case = DescribeInputUseCase(
        detector=RegexFormatDetector(FakeYouTube()),
        file_reader=NoFiles(),
        text_analyzer=SpaCyTextAnalyzer(),
        classifier=InputKindClassifier(),
    )
    return lambda text: use_case.execute(text).kind


# Высказывания: есть подлежащее при сказуемом — это фраза, с точкой или без.
PHRASES_WITH_SUBJECT = [
    "She shrugged off the comment and kept walking.",
    "She shrugged off the comment and kept walking",
    "Her hair was covered in a thick layer of waterproofing wax.",
    "The negotiations were fraught with tension and ambiguity.",
    "I can't afford to squander such a rare opportunity.",
    "He gave in eventually",
    "The plan fell through at the last minute.",
    "His eyes were absorbing the grey color of the clouds above.",
    "The cold water didn't provoke any reaction from Helen.",
    "It's raining cats and dogs.",
    "There is a cat on the roof.",
    "I see.",
    "She smiled.",
    "We need to talk",
    "You should waterproof your boots before wearing them in heavy rain.",
    "\"I'll be back,\" he said.",
    "Are you kidding me?",
    "What are you doing here?",
    "Hello, how are you?",
    "I'm gonna take my horse to the old town road",
    "The kitchen walls were black with cooking grime after years of use.",
    "Dirt had accumulated on the gutter over many seasons.",
    "Prices rose sharply",
    "Nobody knows the answer",
    "Everyone was laughing at him",
    "  She shrugged off the comment.  ",
    "She shrugged off the comment.\n",
]

# Настоящие фразы карточек из книг: подлежащее без артикля, но предложение очевидное.
REAL_CARD_PHRASES = [
    "Effort is the real lever",
    "People adapt quickly to windfalls",
    "satisficers have higher well-being",
    "Slowness makes room for executive function",
    "insurers pay only for brief treatment",
    "criticism makes them defensive or helpless",
    "soldiers live by values larger than themselves",
    "snipers learn to shoot while exhausted",
    "Seligman divides all treatments into curative",
    "Seligman traces the idea to the psychologist",
    "Philosophy is a good preparation to something else",
    "well-being programs work in classrooms",
    "Soldiers first write a eulogy for a fallen friend",
    "MAPP classes run nine hours a day after long flights",
    "Seligman disagrees with his friend, the economist Richard Layard, who argues that "
    "happiness should be the single measure for both personal choices",
    "Seligman also cites the military historian Major General Bob Scales, who argues that "
    "the coming wars are \"human wars,\" which the US has mostly lost",
    "IQ correlates at almost +.50 with choice-reaction time, which means pressing one of "
    "two buttons depending on the colour of a light",
    "Seligman himself, after more than 250,000 bridge hands, knows card distributions instantly",
    "In short: Parents want well-being for their children",
]

# Предложения без подлежащего, но законченные знаком конца: повелительные и восклицания.
PHRASES_BY_PUNCTUATION = [
    "Get out of here!",
    "Don't let them intimidate you, just stand up for yourself.",
    "Never give up!",
    "Take it easy, man.",
    "Mind the gap between the train and the platform.",
    "Stop beating around the bush!",
]

# Запросы-темы: область словаря, ситуация, группа слов, одно слово.
TOPICS = [
    "medicine",
    "procrastinate",
    "waterproofing",
    "job interviews",
    "airport vocabulary",
    "business english",
    "idioms about money",
    "cooking verbs",
    "words for feelings",
    "phrasal verbs with get",
    "make a decision",
    "deal with a difficult boss",
    "how to complain",
    "how to complain about a noisy neighbour",
    "returning an item to a shop",
    "things you say at a party",
    "what to say when you are late",
    "get out of",
    "give up",
    "small talk with colleagues",
    "Top 10 travel phrases",
    "emotions and feelings",
    "renting an apartment",
    "Medicine",
    # spaCy читает их как «подлежащее + сказуемое»: «modal | verbs», «animals | sounds».
    "phrasal verbs with take",
    "modal verbs for advice",
    "slang words teenagers use",
    "animals sounds",
    "irregular verbs",
    "verbs of motion",
    "useful phrases for meetings",
    "idioms that mean happy",
    "words people confuse",
    "british slang",
    "negotiating a salary with an employer",
    "talking to a doctor",
    "ordering food in a restaurant",
    "at the hotel reception",
    "words about weather",
    "verbs that take gerunds",
    "collocations with make and do",
    "expressions for agreeing and disagreeing",
    "office small talk",
    "describing people's appearance",
    "feelings and emotions vocabulary",
    "words used in football",
    "legal english",
    "IT job interview questions",
    "how to say no politely",
    "what to say at a funeral",
    "asking for directions",
    "complaining about service",
    "travel",
    "money",
    "anxiety",
    "break up",
    "look forward to",
    "phrasal verbs for relationships",
    "idioms with animals",
    "academic writing phrases",
    "words teachers use",
    "sounds animals make",
]

# Короткие строки со знаком конца, но без подлежащего: короче минимальной фразы — тема.
TOO_SHORT_FOR_A_PHRASE = [
    "Help!",
    "Thanks.",
    "Get out.",
    "Why not?",
]

# Несколько предложений в одной строке — это уже текст.
TEXT_IN_ONE_LINE = [
    "She shrugged off the comment. Then she kept walking.",
    "I can't believe it! He actually said yes.",
    "It was late. Everyone had gone home. Only the guard remained.",
]


@pytest.mark.parametrize("text", PHRASES_WITH_SUBJECT)
def test_sentence_with_a_subject_is_a_phrase(describe_kind, text: str) -> None:  # noqa: ANN001
    assert describe_kind(text) == InputKind.PHRASE


@pytest.mark.parametrize("text", REAL_CARD_PHRASES)
def test_real_card_phrase_is_a_phrase(describe_kind, text: str) -> None:  # noqa: ANN001
    assert describe_kind(text) == InputKind.PHRASE


@pytest.mark.parametrize("text", PHRASES_BY_PUNCTUATION)
def test_finished_sentence_without_a_subject_is_a_phrase(describe_kind, text: str) -> None:  # noqa: ANN001
    assert describe_kind(text) == InputKind.PHRASE


@pytest.mark.parametrize("text", TOPICS)
def test_query_is_a_topic(describe_kind, text: str) -> None:  # noqa: ANN001
    assert describe_kind(text) == InputKind.TOPIC


@pytest.mark.parametrize("text", TOO_SHORT_FOR_A_PHRASE)
def test_short_exclamation_is_a_topic(describe_kind, text: str) -> None:  # noqa: ANN001
    assert describe_kind(text) == InputKind.TOPIC


@pytest.mark.parametrize("text", TEXT_IN_ONE_LINE)
def test_several_sentences_in_one_line_are_a_text_source(describe_kind, text: str) -> None:  # noqa: ANN001
    assert describe_kind(text) == InputKind.SOURCE

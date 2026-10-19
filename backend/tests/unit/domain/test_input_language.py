import pytest
from backend.domain.services.input_language import is_english


@pytest.mark.parametrize(
    "text",
    [
        "medicine",
        "phrasal verbs with get",
        "She shrugged off the comment and kept walking.",
        "I'm gonna take my horse to the old town road",
        "Don't let them intimidate you!",
        "naïve café résumé",
        "Top 10 travel phrases",
        "  make a decision  ",
        "\"I'll be back,\" he said.",
    ],
)
def test_latin_letters_are_english(text: str) -> None:
    assert is_english(text)


@pytest.mark.parametrize(
    "text",
    [
        "медицина",
        "как пожаловаться начальнику",
        "Как вернуть товар в магазин?",
        "тема: phrasal verbs",
        "фразовые глаголы с get",
        "give up — сдаться",
        "日本語の勉強",
        "Ελληνικά",
        "مرحبا",
        "Ёлка",
    ],
)
def test_any_other_letter_makes_it_not_english(text: str) -> None:
    assert not is_english(text)


@pytest.mark.parametrize("text", ["", "   ", "123", "!!! ???", "2 + 2 = 4", "—"])
def test_without_letters_it_is_not_english(text: str) -> None:
    assert not is_english(text)

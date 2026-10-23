from dataclasses import replace

from backend.domain.entities.token_data import TokenData
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Word


def _token(text: str, lemma: str) -> TokenData:
    return TokenData(
        index=0, text=text, lemma=lemma, pos="".join(["VE", "RB"]), tag="".join(["V", "B"]),
        head_index=0, children_indices=(), is_punct=False, is_stop=False, is_alpha=True,
        is_propn=False, sent_index=0, dep="".join(["RO", "OT"]), whitespace_after=" ",
    )


class TestTokenData:
    def test_keeps_no_dict_per_token(self) -> None:
        assert not hasattr(_token("run", "run"), "__dict__")

    def test_tokens_share_equal_strings(self) -> None:
        first = _token("".join(["ru", "ns"]), "".join(["ru", "n"]))
        second = _token("".join(["r", "uns"]), "".join(["r", "un"]))
        for field in ("text", "lemma", "pos", "tag", "dep", "whitespace_after"):
            assert getattr(first, field) is getattr(second, field), field

    def test_a_replaced_token_shares_its_strings_too(self) -> None:
        token = replace(_token("run", "run"), text="".join(["ra", "n"]))
        assert token.text is _token("".join(["r", "an"]), "run").text


class TestWord:
    def test_keeps_no_dict_and_shares_its_lemma(self) -> None:
        first = Word(0, 4, "".join(["ru", "ns"]), CEFRLevel.A1, 5.0, content=True)
        second = Word(0, 4, "".join(["r", "uns"]), CEFRLevel.A1, 5.0, content=True)
        assert not hasattr(first, "__dict__")
        assert first.lemma is second.lemma

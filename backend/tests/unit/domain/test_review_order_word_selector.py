import pytest
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.services.review_order_word_selector import ReviewOrderWordSelector
from backend.domain.value_objects.cefr_level import CEFRLevel

_LIMIT = 15


def _entry(lemma: str, cefr: CEFRLevel, zipf: float) -> BootstrapWordEntry:
    return BootstrapWordEntry(lemma=lemma, cefr_level=cefr, zipf_value=zipf)


@pytest.mark.unit
class TestReviewOrderWordSelector:
    def setup_method(self) -> None:
        self.selector = ReviewOrderWordSelector()

    def _select(
        self,
        entries: list[BootstrapWordEntry],
        *,
        user_level: CEFRLevel = CEFRLevel.B2,
        frequent_zipf: float | None = None,
        decided: set[str] | None = None,
        excluded: set[str] | None = None,
        limit: int = _LIMIT,
    ) -> list[str]:
        words = self.selector.select_words(
            entries,
            user_level=user_level,
            frequent_zipf=frequent_zipf,
            decided_lemmas=decided or set(),
            excluded_lemmas=excluded or set(),
            limit=limit,
        )
        return [w.lemma for w in words]

    def test_more_frequent_bands_come_first(self) -> None:
        entries = [
            _entry("ubiquitous", CEFRLevel.B2, 3.1),
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("assume", CEFRLevel.B2, 4.7),
        ]

        assert self._select(entries) == ["assume", "elaborate", "ubiquitous"]

    def test_easier_levels_come_first_within_a_band(self) -> None:
        entries = [
            _entry("nuance", CEFRLevel.C1, 4.2),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        assert self._select(entries) == ["elaborate", "nuance"]

    def test_more_frequent_words_come_first_within_a_band_and_level(self) -> None:
        entries = [
            _entry("rarer", CEFRLevel.B2, 3.6),
            _entry("commoner", CEFRLevel.B2, 4.4),
        ]

        assert self._select(entries) == ["commoner", "rarer"]

    def test_frequent_words_go_last(self) -> None:
        entries = [
            _entry("assume", CEFRLevel.B2, 4.7),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        assert self._select(entries, frequent_zipf=4.5) == ["elaborate", "assume"]

    def test_no_threshold_keeps_frequent_words_on_top(self) -> None:
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("assume", CEFRLevel.B2, 4.7),
        ]

        assert self._select(entries, frequent_zipf=None) == ["assume", "elaborate"]

    def test_skips_words_easier_than_the_user_level(self) -> None:
        entries = [
            _entry("run", CEFRLevel.A1, 5.2),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        assert self._select(entries) == ["elaborate"]

    def test_takes_all_harder_levels(self) -> None:
        entries = [_entry("abound", CEFRLevel.C2, 3.2)]

        assert self._select(entries, user_level=CEFRLevel.A1) == ["abound"]

    def test_a_lemma_easier_than_the_user_level_in_one_use_is_skipped(self) -> None:
        entries = [
            _entry("try", CEFRLevel.A1, 5.5),
            _entry("try", CEFRLevel.B2, 5.5),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        assert self._select(entries) == ["elaborate"]

    def test_a_lemma_stands_at_its_easiest_level(self) -> None:
        entries = [
            _entry("abound", CEFRLevel.C2, 4.1),
            _entry("abound", CEFRLevel.C1, 4.1),
            _entry("nuance", CEFRLevel.C2, 4.0),
        ]

        words = self.selector.select_words(
            entries,
            user_level=CEFRLevel.B2,
            frequent_zipf=None,
            decided_lemmas=set(),
            excluded_lemmas=set(),
            limit=_LIMIT,
        )

        assert [(w.lemma, w.cefr_level) for w in words] == [
            ("abound", CEFRLevel.C1),
            ("nuance", CEFRLevel.C2),
        ]

    def test_skips_decided_and_excluded_lemmas(self) -> None:
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
            _entry("abound", CEFRLevel.C2, 3.2),
        ]

        assert self._select(entries, decided={"elaborate"}, excluded={"nuance"}) == ["abound"]

    def test_returns_at_most_the_limit(self) -> None:
        entries = [_entry(f"word{i}", CEFRLevel.B2, 4.0) for i in range(5)]

        assert len(self._select(entries, limit=3)) == 3

    def test_is_deterministic(self) -> None:
        entries = [_entry(lemma, CEFRLevel.B2, 4.0) for lemma in ("gamma", "alpha", "beta")]

        assert self._select(entries) == ["alpha", "beta", "gamma"]

    def test_skips_inflected_forms_of_other_words(self) -> None:
        entries = [
            _entry("play", CEFRLevel.A1, 5.4),
            _entry("playing", CEFRLevel.B2, 5.3),
            _entry("know", CEFRLevel.A1, 6.0),
            _entry("known", CEFRLevel.B2, 5.3),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        assert self._select(entries) == ["elaborate"]

    def test_skips_single_letters(self) -> None:
        entries = [
            _entry("x", CEFRLevel.B2, 5.2),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        assert self._select(entries) == ["elaborate"]

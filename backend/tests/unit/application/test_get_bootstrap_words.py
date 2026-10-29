from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.value_objects.calibration_order import CalibrationOrder
from backend.domain.value_objects.cefr_level import CEFRLevel

from tests.vocabulary_support import user_vocabulary


def _entry(lemma: str, cefr: CEFRLevel, zipf: float) -> BootstrapWordEntry:
    return BootstrapWordEntry(lemma=lemma, cefr_level=cefr, zipf_value=zipf)


@pytest.mark.unit
class TestGetBootstrapWordsUseCase:
    def setup_method(self) -> None:
        self.index_repo = MagicMock()
        self.known_word_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.threshold_resolver = MagicMock()
        self.threshold_resolver.resolve.return_value.zipf = None
        self.corpus_provider = MagicMock()
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = []
        self.use_case = GetBootstrapWordsUseCase(
            index_repo=self.index_repo,
            vocabulary=user_vocabulary(self.known_word_repo),
            settings_repo=self.settings_repo,
            threshold_resolver=self.threshold_resolver,
            corpus_provider=self.corpus_provider,
        )

    def test_computes_grid_levels_from_settings(self) -> None:
        """User CEFR=B2 -> grid={B2, C1, C2}."""
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
            _entry("run", CEFRLevel.A1, 5.2),
        ]

        result = self.use_case.execute(excluded_lemmas=[], order=CalibrationOrder.SPREAD)

        lemmas = {w.lemma for w in result}
        assert "elaborate" in lemmas
        assert "nuance" in lemmas
        assert "run" not in lemmas

    def test_grid_shrinks_for_high_cefr(self) -> None:
        """User CEFR=C1 -> grid={C1, C2}."""
        self.settings_repo.get.return_value = "C1"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        result = self.use_case.execute(excluded_lemmas=[], order=CalibrationOrder.SPREAD)

        lemmas = {w.lemma for w in result}
        assert "elaborate" not in lemmas
        assert "nuance" in lemmas

    def test_a_beginner_calibrates_the_first_levels(self) -> None:
        """User CEFR=A1 -> grid={A1, A2, B1}."""
        self.settings_repo.get.return_value = "A1"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("run", CEFRLevel.A1, 5.2),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        result = self.use_case.execute(excluded_lemmas=[], order=CalibrationOrder.SPREAD)
        lemmas = {w.lemma for w in result}

        assert "run" in lemmas
        assert "elaborate" not in lemmas

    def test_excludes_known_words(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = {"elaborate"}
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        result = self.use_case.execute(excluded_lemmas=[])

        lemmas = {w.lemma for w in result}
        assert "elaborate" not in lemmas

    def test_excludes_words_being_learned(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]
        use_case = GetBootstrapWordsUseCase(
            index_repo=self.index_repo,
            vocabulary=user_vocabulary(self.known_word_repo, learning_lemmas={"nuance"}),
            settings_repo=self.settings_repo,
            threshold_resolver=self.threshold_resolver,
            corpus_provider=self.corpus_provider,
        )

        lemmas = {w.lemma for w in use_case.execute(excluded_lemmas=[])}

        assert lemmas == {"elaborate"}

    def test_passes_excluded_lemmas(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        result = self.use_case.execute(excluded_lemmas=["elaborate"])

        lemmas = {w.lemma for w in result}
        assert "elaborate" not in lemmas

    def test_returns_bootstrap_word_dtos(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        result = self.use_case.execute(excluded_lemmas=[])

        assert len(result) == 1
        dto = result[0]
        assert dto.lemma == "elaborate"
        assert dto.cefr_level == "B2"
        assert dto.zipf_value == 3.8

    def test_review_order_is_the_default(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("ubiquitous", CEFRLevel.C2, 3.1),
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        lemmas = [w.lemma for w in self.use_case.execute(excluded_lemmas=[])]

        assert lemmas == ["elaborate", "nuance", "ubiquitous"]

    def test_review_order_puts_frequent_words_last_at_the_users_threshold(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.threshold_resolver.resolve.return_value.zipf = 4.5
        self.index_repo.get_all_entries.return_value = [
            _entry("career", CEFRLevel.B2, 5.0),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        lemmas = [w.lemma for w in self.use_case.execute(excluded_lemmas=[])]

        assert lemmas == ["elaborate", "career"]

    def test_review_order_returns_one_round(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry(f"word{'x' * i}", CEFRLevel.B2, 4.0) for i in range(40)
        ]

        result = self.use_case.execute(excluded_lemmas=[], order=CalibrationOrder.REVIEW)

        assert len(result) == 15

    def test_review_order_skips_forms_of_dictionary_words_outside_the_index(self) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [("know", "verb")]
        self.index_repo.get_all_entries.return_value = [
            _entry("known", CEFRLevel.B2, 5.3),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        lemmas = [w.lemma for w in self.use_case.execute(excluded_lemmas=[])]

        assert lemmas == ["elaborate"]

    @pytest.mark.parametrize("order", list(CalibrationOrder))
    def test_skips_dictionary_entries_that_are_not_words(self, order: CalibrationOrder) -> None:
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.known_lemmas.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("expect'", CEFRLevel.B2, 4.0),
            _entry("10th", CEFRLevel.B2, 3.9),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        lemmas = [w.lemma for w in self.use_case.execute(excluded_lemmas=[], order=order)]

        assert lemmas == ["elaborate"]

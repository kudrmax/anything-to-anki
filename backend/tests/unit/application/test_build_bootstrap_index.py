from unittest.mock import MagicMock, call

import pytest

from backend.application.use_cases.build_bootstrap_index import BuildBootstrapIndexUseCase
from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus
from backend.domain.value_objects.cefr_level import CEFRLevel


@pytest.mark.unit
class TestBuildBootstrapIndexUseCase:
    def setup_method(self) -> None:
        self.corpus_provider = MagicMock()
        self.cefr_classifier = MagicMock()
        self.frequency_provider = MagicMock()
        self.index_repo = MagicMock()
        self.phrasal_verb_dictionary = MagicMock()
        self.phrasal_verb_dictionary.contains_phrase.return_value = False
        self.use_case = BuildBootstrapIndexUseCase(
            corpus_provider=self.corpus_provider,
            cefr_classifier=self.cefr_classifier,
            frequency_provider=self.frequency_provider,
            index_repo=self.index_repo,
            phrasal_verb_dictionary=self.phrasal_verb_dictionary,
        )

    def test_builds_index_from_corpus(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [
            ("elaborate", "verb"),
            ("elaborate", "adjective"),
            ("nuance", "noun"),
        ]
        self.cefr_classifier.classify.side_effect = lambda lemma, pos: {
            ("elaborate", "verb"): CEFRLevel.B2,
            ("elaborate", "adjective"): CEFRLevel.C1,
            ("nuance", "noun"): CEFRLevel.C1,
        }[(lemma, pos)]
        self.frequency_provider.get_zipf_value.side_effect = lambda lemma: {
            "elaborate": 3.8,
            "nuance": 4.2,
        }[lemma]

        self.use_case.execute()

        calls = self.index_repo.set_meta.call_args_list
        assert calls[0] == call(status=BootstrapIndexStatus.BUILDING)
        assert calls[1].kwargs["status"] == BootstrapIndexStatus.READY
        assert calls[1].kwargs["word_count"] == 3

        rebuild_entries = self.index_repo.rebuild.call_args[0][0]
        assert len(rebuild_entries) == 3

    def test_filters_unknown_cefr(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [("obscure", "adjective")]
        self.cefr_classifier.classify.return_value = CEFRLevel.UNKNOWN
        self.frequency_provider.get_zipf_value.return_value = 3.5

        self.use_case.execute()

        rebuild_entries = self.index_repo.rebuild.call_args[0][0]
        assert len(rebuild_entries) == 0

    def test_filters_zipf_outside_range(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [("the", "determiner")]
        self.cefr_classifier.classify.return_value = CEFRLevel.A1
        self.frequency_provider.get_zipf_value.return_value = 7.5

        self.use_case.execute()

        rebuild_entries = self.index_repo.rebuild.call_args[0][0]
        assert len(rebuild_entries) == 0

    def test_filters_phrasal_verbs(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [
            ("give in", "verb"),
            ("turn down", "phrasal verb"),
        ]
        self.phrasal_verb_dictionary.contains_phrase.side_effect = lambda phrase: phrase in {"give in", "turn down"}
        self.cefr_classifier.classify.return_value = CEFRLevel.B2
        self.frequency_provider.get_zipf_value.return_value = 4.0

        self.use_case.execute()

        rebuild_entries = self.index_repo.rebuild.call_args[0][0]
        assert len(rebuild_entries) == 0

    def test_error_sets_error_status(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.side_effect = RuntimeError("db broken")

        self.use_case.execute()

        calls = self.index_repo.set_meta.call_args_list
        assert calls[1].kwargs["status"] == BootstrapIndexStatus.ERROR
        assert "db broken" in calls[1].kwargs["error"]

    def test_filters_hyphenated_words(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [
            ("brother-in-law", "noun"),
            ("well-known", "adjective"),
            ("elaborate", "verb"),
        ]
        self.cefr_classifier.classify.return_value = CEFRLevel.B2
        self.frequency_provider.get_zipf_value.return_value = 4.0

        self.use_case.execute()

        rebuild_entries = self.index_repo.rebuild.call_args[0][0]
        assert len(rebuild_entries) == 1
        assert rebuild_entries[0].lemma == "elaborate"

    def test_deduplicates_same_lemma_cefr(self) -> None:
        self.corpus_provider.get_all_lemma_pos_pairs.return_value = [
            ("fast", "adjective"),
            ("fast", "adverb"),
        ]
        self.cefr_classifier.classify.return_value = CEFRLevel.A2
        self.frequency_provider.get_zipf_value.return_value = 4.5

        self.use_case.execute()

        rebuild_entries = self.index_repo.rebuild.call_args[0][0]
        assert len(rebuild_entries) == 1

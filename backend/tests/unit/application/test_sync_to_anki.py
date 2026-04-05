from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.domain.entities.dictionary_entry import DictionaryEntry
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import AnkiNotAvailableError
from backend.domain.value_objects.candidate_status import CandidateStatus


def _make_candidate(
    candidate_id: int,
    lemma: str,
    status: CandidateStatus,
    ai_meaning: str | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=1,
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        is_sweet_spot=True,
        context_fragment=f"context with {lemma} here",
        fragment_purity="clean",
        occurrences=1,
        status=status,
        ai_meaning=ai_meaning,
    )


@pytest.mark.unit
class TestSyncToAnkiUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.dictionary_provider = MagicMock()
        self.anki_connector = MagicMock()
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None  # use default deck
        self.dictionary_provider.get_entry.return_value = DictionaryEntry(
            lemma="word", pos="NOUN", definition="a definition", ipa="/wɜːd/"
        )
        self.use_case = SyncToAnkiUseCase(
            candidate_repo=self.candidate_repo,
            dictionary_provider=self.dictionary_provider,
            anki_connector=self.anki_connector,
            settings_repo=self.settings_repo,
        )

    def test_returns_zero_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "word", CandidateStatus.SKIP),
        ]
        result = self.use_case.execute(source_id=1)
        assert result.total == 0
        assert result.added == 0
        self.anki_connector.is_available.assert_not_called()

    def test_raises_when_anki_unavailable(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "word", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = False
        with pytest.raises(AnkiNotAvailableError):
            self.use_case.execute(source_id=1)

    def test_adds_new_cards(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
            _make_candidate(2, "relentless", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.find_notes_by_target.return_value = []
        self.anki_connector.add_notes.return_value = [12345]

        result = self.use_case.execute(source_id=1)

        assert result.total == 2
        assert result.added == 2
        assert result.skipped == 0
        assert result.errors == 0

    def test_skips_duplicates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.side_effect = RuntimeError(
            "AnkiConnect error: ['cannot create note because it is a duplicate']"
        )

        result = self.use_case.execute(source_id=1)

        assert result.total == 1
        assert result.added == 0
        assert result.skipped == 1
        self.anki_connector.find_notes_by_target.assert_not_called()

    def test_counts_errors_when_add_fails(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.find_notes_by_target.return_value = []
        self.anki_connector.add_notes.return_value = [None]  # failure

        result = self.use_case.execute(source_id=1)

        assert result.added == 0
        assert result.errors == 1
        assert result.error_lemmas == ["burnout"]

    def test_duplicate_exception_counts_as_skipped(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "burnout", CandidateStatus.LEARN),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.find_notes_by_target.return_value = []
        self.anki_connector.add_notes.side_effect = RuntimeError(
            "AnkiConnect error: ['cannot create note because it is a duplicate']"
        )

        result = self.use_case.execute(source_id=1)

        assert result.added == 0
        assert result.skipped == 1
        assert result.errors == 0
        assert result.skipped_lemmas == ["burnout"]

    def test_ai_meaning_takes_priority_over_dictionary(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, ai_meaning="бандит, головорез"),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Meaning"] == "бандит, головорез"

    def test_falls_back_to_dictionary_when_no_ai_meaning(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate(1, "thug", CandidateStatus.LEARN, ai_meaning=None),
        ]
        self.anki_connector.is_available.return_value = True
        self.anki_connector.add_notes.return_value = [12345]

        self.use_case.execute(source_id=1)

        call_args = self.anki_connector.add_notes.call_args
        note = call_args.kwargs.get("notes") or call_args[1].get("notes") or call_args[0][2]
        assert note[0]["Meaning"] == "a definition"

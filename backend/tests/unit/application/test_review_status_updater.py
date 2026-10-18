import itertools
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_progress import ReviewProgress
from backend.application.utils.review_status_updater import ReviewStatusUpdater
from backend.domain.value_objects.phrase import Phrase
from backend.domain.value_objects.review_card import CardRow
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.candidate_sorter_support import candidate_sorter
from tests.phrase_support import phrase


def _candidate(status: WordStatus, *, other_new_words: int = 0) -> CardRow:
    card_id = next(_IDS)
    return CardRow(
        source_id=7, word_id=card_id, phrase_id=card_id, lemma="pursuit", pos="NOUN",
        zipf_frequency=3.5, word_status=status, skipped=False,
        phrase=_phrase(other_new_words),
    )


_IDS = itertools.count(1)


def _phrase(other_new_words: int) -> Phrase:
    strange = [f"strange{i}" for i in range(other_new_words)]
    return phrase(" ".join(["the pursuit of", *strange]), "pursuit", new=strange)


def _source(status: SourceStatus) -> MagicMock:
    source = MagicMock()
    source.id = 7
    source.status = status
    return source


@pytest.mark.unit
class TestReviewStatusUpdater:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.card_query = MagicMock()
        elsewhere = MagicMock()
        elsewhere.of_lemmas.side_effect = lambda lemmas: dict.fromkeys(lemmas)
        self.occurrence_repo = MagicMock()
        settings_repo = MagicMock()
        settings_repo.get.return_value = None
        self.updater = ReviewStatusUpdater(
            source_repo=self.source_repo,
            review_progress=ReviewProgress(
                self.card_query, candidate_sorter(settings_repo), elsewhere,
            ),
            occurrence_repo=self.occurrence_repo,
        )

    def test_saves_the_derived_status_when_it_changes(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.DONE)
        self.card_query.shown_cards.return_value = {7: [
            _candidate(WordStatus.LEARN), _candidate(WordStatus.NEW),
        ]}
        self.updater.refresh(7)
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.PARTIALLY_REVIEWED)

    def test_does_not_write_when_the_status_is_unchanged(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.REVIEWED)
        self.card_query.shown_cards.return_value = {7: [_candidate(WordStatus.KNOWN)]}
        self.updater.refresh(7)
        self.source_repo.update_status.assert_not_called()

    def test_ignores_a_missing_source(self) -> None:
        self.source_repo.get_by_id.return_value = None
        self.updater.refresh(7)
        self.source_repo.update_status.assert_not_called()

    def test_cards_with_other_new_words_do_not_hold_the_source(self) -> None:
        self.source_repo.get_by_id.return_value = _source(SourceStatus.PARTIALLY_REVIEWED)
        self.card_query.shown_cards.return_value = {7: [
            _candidate(WordStatus.LEARN),
            _candidate(WordStatus.NEW, other_new_words=1),
        ]}
        self.updater.refresh(7)
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.REVIEWED)

    def test_refresh_all_goes_through_every_source(self) -> None:
        self.source_repo.list_all.return_value = [_source(SourceStatus.DONE)]
        self.card_query.shown_cards.return_value = {7: [_candidate(WordStatus.LEARN)]}
        self.updater.refresh_all()
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.REVIEWED)

    def test_refresh_showing_goes_through_the_sources_whose_cards_show_the_lemmas(self) -> None:
        self.occurrence_repo.sources_showing.return_value = {7}
        self.source_repo.get_by_id.return_value = _source(SourceStatus.DONE)
        self.card_query.shown_cards.return_value = {7: [_candidate(WordStatus.LEARN)]}

        self.updater.refresh_showing({"pursuit"})

        self.occurrence_repo.sources_showing.assert_called_once_with({"pursuit"})
        self.source_repo.list_all.assert_not_called()
        self.source_repo.update_status.assert_called_once_with(7, SourceStatus.REVIEWED)

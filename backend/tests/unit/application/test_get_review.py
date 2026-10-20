from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_review import GetReviewUseCase
from backend.application.utils.card_views import CardViews
from backend.application.utils.review_cards import ReviewCards
from backend.application.utils.source_ordering import SourceOrdering
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import ScopeNotReviewableError, SourceNotFoundError
from backend.domain.services.card_view import Command
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_order import SourceGrouping, SourceSort
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.candidate_sorter_support import candidate_sorter
from tests.card_support import PhraseWordStates, occurrence, word
from tests.source_order_support import order_settings
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate

CLOZE_BUTTON = 1  # Learn, Cloze, Known, Skip
COLLECTION = 7


def _text(source_id: int, status: SourceStatus = SourceStatus.DONE, **changes: object) -> Source:
    return Source(
        id=source_id, status=status, format=Format.PLAIN, kind=Kind.TEXT,
        **changes,  # type: ignore[arg-type]
    )


@pytest.mark.unit
class TestGetReviewUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.collection_repo = MagicMock()
        self.collection_repo.list_all.return_value = [Collection(id=COLLECTION, name="Show")]
        self.words: dict[int, list[StoredCandidate]] = {}
        self.candidate_repo = MagicMock()
        self.candidate_repo.get_by_source.side_effect = lambda sid: self.words.get(sid, [])
        self.occurrence_repo = MagicMock()
        self.occurrence_repo.shown_by_word.return_value = {}
        self.settings_repo = MagicMock()
        self.settings_repo.get.return_value = None
        self.job_repo = MagicMock()
        self.job_repo.get_jobs_for_phrases.return_value = {}
        self.job_repo.get_jobs_for_candidates.return_value = {}
        self.report_repo = MagicMock()
        self.report_repo.reported_phrase_ids.return_value = set()
        self.card_query = MagicMock()
        self.card_query.learn_counts.return_value = {}
        self.lock = MagicMock()
        self.lock.operations.return_value = {}
        self.order_settings = order_settings(SourceGrouping.NONE, SourceSort.ADDED)
        resolver = SourceScopeResolver(
            self.source_repo, self.collection_repo,
            SourceOrdering(
                self.order_settings, MagicMock(), MagicMock(), self.candidate_repo,
            ),
        )
        self.use_case = GetReviewUseCase(
            card_views=CardViews(
                review_cards=ReviewCards(
                    self.candidate_repo, self.occurrence_repo,
                    PhraseWordStates(
                        lambda: [w for ws in self.words.values() for w in ws],
                        lambda word_id: self.occurrence_repo.shown_by_word.return_value.get(
                            word_id, [],
                        ),
                    ),
                    user_vocabulary(),
                ),
                candidate_sorter=candidate_sorter(self.settings_repo),
                job_repo=self.job_repo,
                report_repo=self.report_repo,
                scope_resolver=resolver,
                source_repo=self.source_repo,
            ),
            scope_resolver=resolver,
            card_query=self.card_query,
            lock=self.lock,
        )

    def _one_source(self, source: Source) -> None:
        self.source_repo.get_by_id.return_value = source

    def _collection(self) -> None:
        self.source_repo.list_all.return_value = [
            _text(
                2, SourceStatus.ERROR, collection_id=COLLECTION, title="Episode 2",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            _text(
                1, collection_id=COLLECTION, title="Pilot",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]
        self.words = {1: [word(5, "glare", source_id=1)]}
        shown = {5: [occurrence(5, 5)]}
        self.occurrence_repo.shown_by_word.return_value = shown
        self.occurrence_repo.shown_by_word.side_effect = lambda sid: shown if sid == 1 else {}
        self.card_query.learn_counts.return_value = {1: 2, 2: 1}

    def test_collection_review_sums_its_sources(self) -> None:
        self._collection()
        review = self.use_case.execute(SourceScope.collection(COLLECTION))
        assert review.scope == str(COLLECTION)
        assert review.title == "Show"
        assert review.status == "done"
        assert [c.source.id for c in review.candidates] == [1]
        assert review.learn_count == 3
        assert (review.progress.decided, review.progress.total) == (0, 1)
        self.card_query.learn_counts.assert_called_once_with([2, 1])

    def test_a_collection_review_follows_its_sources_in_the_users_order(self) -> None:
        self.source_repo.list_all.return_value = [
            _text(
                2, collection_id=COLLECTION, title="Zulu",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
            ),
            _text(
                1, collection_id=COLLECTION, title="Alpha",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ]
        self.words = {
            1: [word(5, "glare", source_id=1)], 2: [word(6, "quill", source_id=2)],
        }
        self.occurrence_repo.shown_by_word.return_value = {
            5: [occurrence(5, 5)], 6: [occurrence(6, 6)],
        }
        self.candidate_repo.last_studied.return_value = {
            1: datetime(2026, 2, 1, 12, 0, tzinfo=UTC),
        }
        by = {
            SourceSort.ADDED: [2, 1],
            SourceSort.NAME: [1, 2],
            SourceSort.LAST_STUDIED: [1, 2],
        }
        for sort, expected in by.items():
            self.order_settings.set("source_sort", sort.value)
            review = self.use_case.execute(
                SourceScope.collection(COLLECTION),
                sort_order=CandidateSortOrder.CHRONOLOGICAL,
            )
            assert [c.source.id for c in review.candidates] == expected, sort

    def test_busy_when_any_source_is_held(self) -> None:
        self._collection()
        self.lock.operations.return_value = {2: HeldOperation(kind=SourceOperationKind.REBUILD)}
        review = self.use_case.execute(SourceScope.collection(COLLECTION))
        assert review.busy is True

    def test_free_set_is_not_busy(self) -> None:
        self._collection()
        assert self.use_case.execute(SourceScope.collection(COLLECTION)).busy is False

    def test_unsorted_is_not_for_review(self) -> None:
        with pytest.raises(ScopeNotReviewableError):
            self.use_case.execute(SourceScope.unsorted())

    def test_source_review_carries_its_token_and_title(self) -> None:
        self._one_source(_text(1, title="Pilot"))
        review = self.use_case.execute(SourceScope.source(1))
        assert (review.scope, review.title) == ("source-1", "Pilot")

    def test_the_review_reads_its_status_from_its_progress(self) -> None:
        self._one_source(_text(1))
        self.words = {1: [word(1, "burnout", status=WordStatus.LEARN, source_id=1)]}
        self.occurrence_repo.shown_by_word.return_value = {1: [occurrence(1, 1)]}
        assert self.use_case.execute(SourceScope.source(1)).status == "reviewed"

    def test_shows_first_fifteen_candidates_by_relevance(self) -> None:
        self._one_source(_text(1))
        assert self.use_case.execute(SourceScope.source(1)).initially_shown_candidates == 15

    def test_shows_all_candidates_in_text_order(self) -> None:
        self._one_source(_text(1))
        review = self.use_case.execute(
            SourceScope.source(1), sort_order=CandidateSortOrder.CHRONOLOGICAL,
        )
        assert review.initially_shown_candidates is None

    def test_shows_first_fifteen_candidates_by_key_words(self) -> None:
        self._one_source(_text(1))
        review = self.use_case.execute(
            SourceScope.source(1), sort_order=CandidateSortOrder.KEY_WORDS,
        )
        assert review.initially_shown_candidates == 15

    def test_forbids_new_markup_only_for_a_cloze_in_anki(self) -> None:
        """Q11: a Learn card in Anki may still become a cloze (a new note)."""
        self._one_source(_text(1))
        self.words = {1: [
            word(1, "burnout", status=WordStatus.LEARNING, source_id=1),
            word(2, "lizard", status=WordStatus.LEARN, source_id=1),
            word(3, "gecko", status=WordStatus.LEARNING, source_id=1),
        ]}
        self.occurrence_repo.shown_by_word.return_value = {
            1: [occurrence(1, 1, exported=True, decision_kind=DecisionKind.CLOZE)],
            2: [occurrence(2, 2)],
            3: [occurrence(3, 3, exported=True)],
        }
        result = self.use_case.execute(SourceScope.source(1))
        cloze = {
            c.phrase_id: (c.can_edit_cloze, c.state.buttons[CLOZE_BUTTON].command)
            for c in result.candidates
        }
        # P17 on the cloze in Anki undoes it; P18 on the Learn in Anki makes a cloze.
        assert (cloze[1], cloze[3]) == ((False, Command.DECIDE), (False, Command.EDIT_CLOZE))

    def test_source_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.execute(SourceScope.source(999))

    def test_card_carries_its_source(self) -> None:
        self._one_source(_text(1))
        self.lock.operations.return_value = {1: HeldOperation(kind=SourceOperationKind.REBUILD)}
        self.words = {1: [word(5, "glare", source_id=1)]}
        self.occurrence_repo.shown_by_word.return_value = {5: [occurrence(5, 5)]}
        review = self.use_case.execute(SourceScope.source(1))
        [card] = review.candidates
        assert card.source.id == 1
        assert review.busy is True

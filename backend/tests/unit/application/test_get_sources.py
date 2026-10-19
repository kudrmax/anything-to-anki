from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.utils.card_views import CardViews
from backend.application.utils.review_cards import ReviewCards
from backend.application.utils.review_progress import ReviewProgress
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.application.utils.topic_generation import TopicGenerationProbe
from backend.domain.entities.collection import Collection
from backend.domain.entities.source import Source
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.card_view import Command
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.held_operation import HeldOperation
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.review_card import CardRow
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.candidate_sorter_support import candidate_sorter
from tests.card_support import PhraseWordStates, occurrence, word
from tests.phrase_support import phrase
from tests.vocabulary_support import user_vocabulary

CLOZE_BUTTON = 1  # Learn, Cloze, Known, Skip


def _row(
    source_id: int, phrase_id: int, status: WordStatus = WordStatus.NEW,
) -> CardRow:
    return CardRow(
        source_id=source_id, word_id=phrase_id, phrase_id=phrase_id, lemma=f"word{phrase_id}",
        pos="NOUN", zipf_frequency=4.0, word_status=status, skipped=False,
        phrase=phrase(f"a word{phrase_id}", f"word{phrase_id}"),
    )


def _text(source_id: int, status: SourceStatus = SourceStatus.DONE) -> Source:
    return Source(id=source_id, status=status, format=Format.PLAIN, kind=Kind.TEXT)


@pytest.mark.unit
class TestGetSourcesUseCase:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.candidate_repo = MagicMock()
        self.candidate_repo.get_by_source.return_value = []
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
        self.card_query.shown_cards.return_value = {}
        self.card_query.learn_counts.return_value = {}
        self.collection_repo = MagicMock()
        self.collection_repo.list_all.return_value = []
        self.topic_target_repo = MagicMock()
        self.topic_target_repo.has_targets.return_value = False
        self.lock = MagicMock()
        self.lock.operations.return_value = {}
        elsewhere = MagicMock()
        elsewhere.of_lemmas.side_effect = lambda lemmas: dict.fromkeys(lemmas)
        sorter = candidate_sorter(self.settings_repo)
        self.use_case = GetSourcesUseCase(
            source_repo=self.source_repo,
            scope_resolver=SourceScopeResolver(self.source_repo, self.collection_repo),
            generation_probe=TopicGenerationProbe(self.job_repo, self.topic_target_repo),
            review_progress=ReviewProgress(self.card_query, sorter, elsewhere),
            card_query=self.card_query,
            card_views=CardViews(
                review_cards=ReviewCards(
                    self.candidate_repo, self.occurrence_repo,
                    PhraseWordStates(
                        lambda: self.candidate_repo.get_by_source.return_value,
                        lambda word_id: self.occurrence_repo.shown_by_word.return_value.get(
                            word_id, [],
                        ),
                    ),
                    user_vocabulary(),
                ),
                candidate_sorter=sorter,
                job_repo=self.job_repo,
                report_repo=self.report_repo,
            ),
            lock=self.lock,
        )

    def test_list_all(self) -> None:
        self.source_repo.list_all.return_value = [
            _text(1, SourceStatus.NEW), _text(2),
        ]
        result = self.use_case.list_all()
        assert len(result) == 2
        assert result[0].id == 1

    def test_board_groups_scope_by_stage_and_filters_by_title(self) -> None:
        self.collection_repo.list_all.return_value = [
            Collection(id=1, name="Friends"), Collection(id=2, name="Season 1", parent_id=1),
        ]
        self.source_repo.list_all.return_value = [
            Source(id=1, title="Pilot", status=SourceStatus.DONE, collection_id=2),
            Source(id=2, title="Sonogram", status=SourceStatus.NEW, collection_id=2),
            Source(id=3, title="Essay", status=SourceStatus.DONE),
        ]
        # A source with a ready card left to decide is ready for review.
        self.card_query.shown_cards.return_value = {1: [_row(1, 1)]}

        board = self.use_case.board(SourceScope.collection(1))

        assert board.title == "Friends"
        assert [(g.stage, [s.title for s in g.sources]) for g in board.groups] == [
            ("preparing", ["Sonogram"]),
            ("ready", ["Pilot"]),
        ]
        assert board.groups[1].sources[0].collection_path == ["Friends", "Season 1"]

        found = self.use_case.board(SourceScope.all(), query="SONO")
        assert [s.title for g in found.groups for s in g.sources] == ["Sonogram"]

    def test_the_board_reads_all_its_sources_at_once(self) -> None:
        self.source_repo.list_all.return_value = [_text(1), _text(2), _text(3)]
        self.use_case.board(SourceScope.all())
        self.card_query.shown_cards.assert_called_once_with([1, 2, 3])
        self.card_query.learn_counts.assert_called_once_with([1, 2, 3])
        self.lock.operations.assert_called_once_with()
        self.candidate_repo.get_by_source.assert_not_called()
        self.occurrence_repo.shown_by_word.assert_not_called()

    def test_topic_without_targets_awaits_generation(self) -> None:
        from datetime import UTC, datetime

        from backend.domain.entities.job import Job
        from backend.domain.value_objects.job_status import JobStatus
        from backend.domain.value_objects.job_type import JobType

        self.source_repo.list_all.return_value = [
            Source(
                id=5, status=SourceStatus.NEW, role=SourceRole.TOPIC, topic_query="salary talk",
            ),
        ]
        self.job_repo.get_jobs_by_status.return_value = [
            Job(id=1, job_type=JobType.TOPIC_TARGETS, candidate_id=None, source_id=5,
                status=JobStatus.FAILED, error="timeout",
                created_at=datetime.now(tz=UTC), started_at=None),
        ]

        [dto] = self.use_case.list_all()

        assert dto.awaiting_generation is True
        assert dto.generation_status == "failed"
        assert dto.generation_error == "timeout"

    def test_topic_with_targets_and_regular_sources_need_no_generation(self) -> None:
        self.source_repo.list_all.return_value = [
            Source(
                id=5, status=SourceStatus.NEW, role=SourceRole.TOPIC, topic_query="salary talk",
            ),
            _text(6, SourceStatus.NEW),
        ]
        self.topic_target_repo.has_targets.return_value = True

        result = self.use_case.list_all()

        assert [dto.awaiting_generation for dto in result] == [False, False]
        assert [dto.generation_status for dto in result] == [None, None]
        self.job_repo.get_jobs_by_status.assert_not_called()

    def test_list_all_counts_cards_and_learn_words(self) -> None:
        self.source_repo.list_all.return_value = [_text(1)]
        self.card_query.shown_cards.return_value = {1: [
            _row(1, 1, WordStatus.LEARN),
            _row(1, 2, WordStatus.LEARN),
            _row(1, 3),
            _row(1, 4, WordStatus.KNOWN),
        ]}
        self.card_query.learn_counts.return_value = {1: 2}
        result = self.use_case.list_all()
        assert result[0].candidate_count == 4
        assert result[0].learn_count == 2
        assert (result[0].progress.decided, result[0].progress.total) == (3, 4)
        # The review status is what the progress says when the source is read: nothing
        # stores it.
        assert result[0].status == "partially_reviewed"
        assert result[0].stage == "in_progress"
        self.source_repo.update_status.assert_not_called()

    def test_a_source_says_what_it_allows_and_how_far_its_review_is(self) -> None:
        self.source_repo.list_all.return_value = [
            _text(1, SourceStatus.NEW), _text(2), _text(3),
        ]
        self.card_query.shown_cards.return_value = {
            2: [_row(2, 1, WordStatus.LEARN), _row(2, 2)],
            3: [_row(3, 3, WordStatus.KNOWN)],
        }
        self.card_query.learn_counts.return_value = {2: 1}
        self.lock.operations.return_value = {1: HeldOperation(SourceOperationKind.PROCESS)}

        new, started, reviewed = self.use_case.list_all()

        assert (new.can_review, new.can_export, new.can_delete) == (False, False, False)
        assert (started.can_review, started.can_export, started.can_delete) == (True, True, True)
        assert started.review_fraction == 0.5
        # Every card decided, but only Known: nothing to export.
        assert (reviewed.status, reviewed.can_export, reviewed.review_fraction) == (
            "reviewed", False, 1.0,
        )

    def test_a_source_with_nothing_decided_cannot_be_exported(self) -> None:
        self.source_repo.list_all.return_value = [_text(1)]
        self.card_query.shown_cards.return_value = {1: [_row(1, 1), _row(1, 2)]}
        [dto] = self.use_case.list_all()
        assert (dto.status, dto.stage, dto.can_review, dto.can_export) == (
            "done", "ready", True, False,
        )

    def test_the_detail_reads_the_review_status_from_its_progress(self) -> None:
        self.source_repo.get_by_id.return_value = _text(1)
        self.candidate_repo.get_by_source.return_value = [
            word(1, "burnout", status=WordStatus.LEARN),
        ]
        self.occurrence_repo.shown_by_word.return_value = {1: [occurrence(1, 1)]}
        assert self.use_case.get_by_id(1).status == "reviewed"

    def test_a_busy_source_offers_its_operation_but_it_cant_start(self) -> None:
        self.source_repo.list_all.return_value = [_text(1)]
        self.lock.operations.return_value = {1: HeldOperation(SourceOperationKind.REBUILD)}
        [dto] = self.use_case.list_all()
        assert dto.busy_with is SourceOperationKind.REBUILD
        assert dto.available_operation is SourceOperationKind.REBUILD
        assert dto.can_start_operation is False
        assert dto.operation_hint == "Wait until the rebuild finishes"
        assert dto.progress_caption == "Rebuilding…"

    def test_a_free_source_can_start_its_operation(self) -> None:
        self.source_repo.list_all.return_value = [_text(1)]
        self.lock.operations.return_value = {}
        [dto] = self.use_case.list_all()
        assert dto.available_operation is SourceOperationKind.REBUILD
        assert dto.can_start_operation is True
        assert dto.operation_hint is None

    def test_the_caption_says_where_the_review_is(self) -> None:
        self.source_repo.list_all.return_value = [
            _text(1), _text(2), _text(3), _text(4),
        ]
        self.lock.operations.return_value = {}
        self.card_query.shown_cards.return_value = {
            2: [_row(2, 1), _row(2, 2)],
            3: [_row(3, 3, WordStatus.LEARN), _row(3, 4)],
            4: [_row(4, 5, WordStatus.LEARN)],
        }
        self.card_query.learn_counts.return_value = {4: 1}
        captions = [dto.progress_caption for dto in self.use_case.list_all()]
        assert captions == ["Nothing to learn", "2 phrases", "1 of 2 decided", "1 to learn"]

    def test_get_by_id_found(self) -> None:
        self.source_repo.get_by_id.return_value = _text(1)
        result = self.use_case.get_by_id(1)
        assert result.id == 1

    def test_get_by_id_shows_first_fifteen_candidates_by_relevance(self) -> None:
        self.source_repo.get_by_id.return_value = _text(1)
        assert self.use_case.get_by_id(1).initially_shown_candidates == 15

    def test_get_by_id_shows_all_candidates_in_text_order(self) -> None:
        self.source_repo.get_by_id.return_value = _text(1)
        result = self.use_case.get_by_id(1, sort_order=CandidateSortOrder.CHRONOLOGICAL)
        assert result.initially_shown_candidates is None

    def test_get_by_id_shows_first_fifteen_candidates_by_key_words(self) -> None:
        self.source_repo.get_by_id.return_value = _text(1)
        result = self.use_case.get_by_id(1, sort_order=CandidateSortOrder.KEY_WORDS)
        assert result.initially_shown_candidates == 15

    def test_get_by_id_forbids_new_markup_only_for_a_cloze_in_anki(self) -> None:
        """Q11: a Learn card in Anki may still become a cloze (a new note)."""
        self.source_repo.get_by_id.return_value = _text(1)
        self.candidate_repo.get_by_source.return_value = [
            word(1, "burnout", status=WordStatus.LEARNING),
            word(2, "lizard", status=WordStatus.LEARN),
            word(3, "gecko", status=WordStatus.LEARNING),
        ]
        self.occurrence_repo.shown_by_word.return_value = {
            1: [occurrence(1, 1, exported=True, decision_kind=DecisionKind.CLOZE)],
            2: [occurrence(2, 2)],
            3: [occurrence(3, 3, exported=True)],
        }
        result = self.use_case.get_by_id(1)
        cloze = {
            c.phrase_id: (c.can_edit_cloze, c.state.buttons[CLOZE_BUTTON].command)
            for c in result.candidates
        }
        # P17 on the cloze in Anki undoes it; P18 on the Learn in Anki makes a cloze.
        assert (cloze[1], cloze[3]) == ((False, Command.DECIDE), (False, Command.EDIT_CLOZE))

    def test_get_by_id_not_found(self) -> None:
        self.source_repo.get_by_id.return_value = None
        with pytest.raises(SourceNotFoundError):
            self.use_case.get_by_id(999)

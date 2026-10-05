from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.dto.cloze_dtos import ClozeWordDTO, PreviewClozeRequest
from backend.application.use_cases.preview_cloze import PreviewClozeUseCase
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError, InvalidClozeError
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

pytestmark = pytest.mark.unit

GIVE_UP = "She finally gave up smoking last year."


def _candidate(
    *,
    translation: str | None = "бросить",
    synonyms: str = "quit, stop",
    cloze: CandidateCloze | None = None,
    with_meaning: bool = True,
) -> StoredCandidate:
    meaning = CandidateMeaning(
        candidate_id=1, meaning="To stop.", translation=translation,
        synonyms=synonyms, examples=None, ipa=None, generated_at=None,
    ) if with_meaning else None
    return StoredCandidate(
        id=1, source_id=5, lemma="give up", pos="VERB", cefr_level="B1",
        zipf_frequency=4.0, context_fragment=GIVE_UP, fragment_purity="clean",
        occurrences=1, status=CandidateStatus.LEARN, surface_form="gave up",
        is_phrasal_verb=True, meaning=meaning, cloze=cloze,
    )


class TestPreviewCloze:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.default_hint = "none"
        self.settings_repo.get.side_effect = lambda key, default=None: (
            self.default_hint if key == "cloze_default_hint" else default
        )
        self.candidate_repo.get_by_id.return_value = _candidate()
        self.use_case = PreviewClozeUseCase(
            candidate_repo=self.candidate_repo,
            settings_repo=self.settings_repo,
            builder=ClozeBuilder(),
        )

    def test_preview_defaults_to_target_and_setting_hint(self) -> None:
        self.default_hint = "first_letter"
        preview = self.use_case.execute(1, PreviewClozeRequest())
        assert preview.hidden_word_indices == [2, 3]
        assert preview.hint_kind == "first_letter"
        assert preview.hint == "g… u…"
        assert preview.front == "She finally […] smoking last year."
        assert preview.words[2] == ClozeWordDTO(index=2, text="gave", is_target=True)
        assert preview.words[0] == ClozeWordDTO(index=0, text="She", is_target=False)
        assert preview.available_hints == [
            "none", "translation", "synonyms", "first_letter", "custom",
        ]

    def test_preview_ignores_corrupt_default_hint_setting(self) -> None:
        self.default_hint = "bogus"
        preview = self.use_case.execute(1, PreviewClozeRequest())
        assert preview.hint_kind == "none"

    def test_preview_falls_back_to_none_when_default_unavailable(self) -> None:
        self.default_hint = "translation"
        self.candidate_repo.get_by_id.return_value = _candidate(with_meaning=False)
        preview = self.use_case.execute(1, PreviewClozeRequest())
        assert preview.hint_kind == "none"
        assert preview.hint == ""
        assert "translation" not in preview.available_hints

    def test_preview_uses_request_indices(self) -> None:
        preview = self.use_case.execute(1, PreviewClozeRequest(hidden_word_indices=[3]))
        assert preview.hidden_word_indices == [3]
        assert preview.front == "She finally gave […] smoking last year."

    def test_preview_uses_request_hint_and_custom_text(self) -> None:
        preview = self.use_case.execute(
            1, PreviewClozeRequest(hint_kind="custom", custom_hint=" stop it "),
        )
        assert preview.hint_kind == "custom"
        assert preview.hint == "stop it"
        assert preview.custom_hint == " stop it "

    def test_preview_uses_stored_markup(self) -> None:
        self.candidate_repo.get_by_id.return_value = _candidate(
            cloze=CandidateCloze(1, (4,), ClozeHintKind.CUSTOM, "a habit", GIVE_UP),
        )
        preview = self.use_case.execute(1, PreviewClozeRequest())
        assert preview.hidden_word_indices == [4]
        assert preview.hint_kind == "custom"
        assert preview.custom_hint == "a habit"
        assert preview.hint == "a habit"

    def test_preview_rebuilds_stale_markup(self) -> None:
        self.candidate_repo.get_by_id.return_value = _candidate(
            cloze=CandidateCloze(
                1, (0,), ClozeHintKind.NONE, None, "Old phrase where she gave up.",
            ),
        )
        preview = self.use_case.execute(1, PreviewClozeRequest())
        assert preview.hidden_word_indices == [2, 3]

    def test_preview_allows_empty_indices(self) -> None:
        preview = self.use_case.execute(1, PreviewClozeRequest(hidden_word_indices=[]))
        assert preview.hidden_word_indices == []
        assert preview.front == GIVE_UP

    def test_preview_drops_leaking_hint_to_none(self) -> None:
        self.candidate_repo.get_by_id.return_value = _candidate(synonyms="give up, quit")
        preview = self.use_case.execute(1, PreviewClozeRequest(hint_kind="synonyms"))
        assert preview.hint_kind == "none"
        assert "synonyms" not in preview.available_hints

    def test_preview_rejects_out_of_range_indices(self) -> None:
        with pytest.raises(InvalidClozeError):
            self.use_case.execute(1, PreviewClozeRequest(hidden_word_indices=[42]))

    def test_preview_missing_candidate(self) -> None:
        self.candidate_repo.get_by_id.return_value = None
        with pytest.raises(CandidateNotFoundError):
            self.use_case.execute(1, PreviewClozeRequest())


def test_preview_request_rejects_unknown_hint_kind() -> None:
    with pytest.raises(ValueError, match="hint"):
        PreviewClozeRequest(hint_kind="bogus")

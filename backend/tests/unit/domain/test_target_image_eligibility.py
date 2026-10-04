from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus

pytestmark = pytest.mark.unit


def _candidate(pos: str, *, is_phrasal_verb: bool = False) -> StoredCandidate:
    return StoredCandidate(
        source_id=1, lemma="ladder", pos=pos, cefr_level="B1", zipf_frequency=3.5,
        context_fragment="climb the ladder", fragment_purity="clean", occurrences=1,
        status=CandidateStatus.PENDING, is_phrasal_verb=is_phrasal_verb,
    )


class TestTargetImageEligibility:
    def test_noun_can_have_picture(self) -> None:
        assert _candidate("NOUN").can_have_target_image

    @pytest.mark.parametrize("pos", ["VERB", "ADJ", "ADV", "X"])
    def test_other_parts_of_speech_cannot(self, pos: str) -> None:
        assert not _candidate(pos).can_have_target_image

    def test_phrasal_verb_cannot(self) -> None:
        assert not _candidate("NOUN", is_phrasal_verb=True).can_have_target_image

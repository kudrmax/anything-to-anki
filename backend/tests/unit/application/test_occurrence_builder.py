import pytest
from backend.application.dto.analysis_dtos import OccurrenceDTO, OccurrenceKeyDTO, WordDTO
from backend.application.dto.cefr_dtos import breakdown_to_dto
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.application.utils.occurrence_builder import OccurrenceBuilder
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.usage_distribution import UsageDistribution

from tests.phrase_support import phrase
from tests.rebuild_support import breakdown


@pytest.mark.unit
def test_a_word_of_the_analysis_becomes_a_built_word_with_every_occurrence() -> None:
    levels = breakdown(CEFRLevel.C1, {CEFRLevel.C1: 1.0})
    dto = WordDTO(
        lemma="Glare", is_phrasal_verb=False, pos="VERB", cefr_level="C1",
        cefr_breakdown=breakdown_to_dto(levels), zipf_frequency=3.1,
        usage_distribution={"informal": 1.0},
        occurrences=[
            OccurrenceDTO(
                phrase=phrase("He glared.", "glared"),
                phrase_position=DocumentPositionDTO(
                    block=0, start_line=1, start_char=2, end_line=1, end_char=12,
                ),
                key=OccurrenceKeyDTO(block=0, line=1, char=5),
                fragment_score=0.25,
            ),
            OccurrenceDTO(
                phrase=phrase("She glared back.", "glared"),
                phrase_position=DocumentPositionDTO(
                    block=2, start_line=0, start_char=0, end_line=0, end_char=16,
                ),
                key=OccurrenceKeyDTO(block=2, line=0, char=4),
                fragment_score=0.5,
            ),
        ],
    )

    [built] = OccurrenceBuilder().words([dto])

    assert built.key == WordKey("glare", False)
    assert (built.pos, built.cefr_level, built.zipf_frequency) == ("VERB", "C1", 3.1)
    assert built.usage_distribution == UsageDistribution({"informal": 1.0})
    assert built.cefr_breakdown is not None
    assert built.cefr_breakdown.reduced() == levels.reduced()
    assert built.data.occurrence_count == 2
    first, second = built.occurrences
    assert first.phrase == phrase("He glared.", "glared")
    assert first.phrase_position == DocumentPosition(0, 1, 2, 1, 12)
    assert first.key == OccurrenceKey(block=0, line=1, char=5)
    assert first.fragment_score == 0.25
    assert second.key == OccurrenceKey(block=2, line=0, char=4)

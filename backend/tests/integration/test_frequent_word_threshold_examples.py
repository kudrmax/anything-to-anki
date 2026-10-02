import pytest
from backend.domain.value_objects.frequent_word_threshold import (
    FREQUENT_WORD_THRESHOLDS,
    FrequentWordThreshold,
)
from wordfreq import zipf_frequency

ZIPF_STEP = 0.5
STRICTEST_ZIPF = max(t.zipf for t in FREQUENT_WORD_THRESHOLDS if t.zipf is not None)


@pytest.mark.integration
@pytest.mark.parametrize(
    "threshold",
    [t for t in FREQUENT_WORD_THRESHOLDS if t.zipf is not None],
    ids=lambda t: t.key,
)
def test_examples_go_down_exactly_at_this_threshold(threshold: FrequentWordThreshold) -> None:
    assert threshold.zipf is not None
    assert threshold.examples
    for word in threshold.examples:
        zipf = zipf_frequency(word, "en")
        assert threshold.covers(zipf), word
        if threshold.zipf < STRICTEST_ZIPF:
            assert zipf < threshold.zipf + ZIPF_STEP, word

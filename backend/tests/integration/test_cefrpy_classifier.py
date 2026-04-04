import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cefrpy_classifier import CefrpyCEFRClassifier


@pytest.mark.integration
class TestCefrpyClassifier:
    def setup_method(self) -> None:
        self.classifier = CefrpyCEFRClassifier()

    def test_common_word_low_level(self) -> None:
        level = self.classifier.classify("happy", "JJ")
        assert level in (CEFRLevel.A1, CEFRLevel.A2)

    def test_advanced_word_high_level(self) -> None:
        level = self.classifier.classify("ubiquitous", "JJ")
        assert level.value >= CEFRLevel.B2.value

    def test_unknown_word_returns_unknown(self) -> None:
        level = self.classifier.classify("asdfghjkl", "NN")
        assert level is CEFRLevel.UNKNOWN

    def test_fallback_to_average(self) -> None:
        # "run" with an unusual POS tag should fallback to average
        level = self.classifier.classify("run", "XX")
        # Should find it via average, not UNKNOWN
        assert level is not CEFRLevel.UNKNOWN

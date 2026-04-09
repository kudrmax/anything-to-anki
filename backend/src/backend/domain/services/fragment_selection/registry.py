"""Flat registries mapping config names to implementations."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.cleanup.rules import (
    LeftCconjSconjRule,
    LeftRelativizerRule,
    PunctuationRule,
    RightCconjSconjDetIntjRule,
    RightDanglingAdpRule,
    RightDanglingAuxPartRule,
    RightDanglingSubjectPronounRule,
    RightPossessivePronounRule,
    RightRelativePronounRule,
)
from backend.domain.services.fragment_selection.sources.ancestor_chain import (
    AncestorChainSource,
)
from backend.domain.services.fragment_selection.sources.legacy_extractor import (
    LegacyExtractorSource,
)
from backend.domain.services.fragment_selection.sources.sentence import (
    SentenceSource,
)
from backend.domain.services.fragment_selection.sources.verb_subtree import (
    VerbSubtreeSource,
)

if TYPE_CHECKING:
    from backend.domain.services.fragment_selection.cleanup.rules import StripRule
    from backend.domain.services.fragment_selection.sources.base import (
        CandidateSource,
    )
    from backend.domain.value_objects.fragment_selection_config import (
        CandidateSourcesConfig,
        CleanupConfig,
    )


StripRuleFactory = type[
    PunctuationRule
    | LeftCconjSconjRule
    | LeftRelativizerRule
    | RightCconjSconjDetIntjRule
    | RightDanglingAdpRule
    | RightDanglingSubjectPronounRule
    | RightRelativePronounRule
    | RightPossessivePronounRule
    | RightDanglingAuxPartRule
]

STRIP_RULES: dict[str, StripRuleFactory] = {
    "punctuation": PunctuationRule,
    "left_cconj_sconj": LeftCconjSconjRule,
    "left_relativizer": LeftRelativizerRule,
    "right_cconj_sconj_det_intj": RightCconjSconjDetIntjRule,
    "right_dangling_adp": RightDanglingAdpRule,
    "right_dangling_subject_pronoun": RightDanglingSubjectPronounRule,
    "right_relative_pronoun": RightRelativePronounRule,
    "right_possessive_pronoun": RightPossessivePronounRule,
    "right_dangling_aux_part": RightDanglingAuxPartRule,
}


def build_strip_rules(config: CleanupConfig) -> list[StripRule]:
    """Instantiate enabled strip rules in config order."""
    return [STRIP_RULES[name](config) for name in config.enabled_rules]


CandidateSourceFactory = type[
    VerbSubtreeSource
    | AncestorChainSource
    | SentenceSource
    | LegacyExtractorSource
]

CANDIDATE_SOURCES: dict[str, CandidateSourceFactory] = {
    "verb_subtree": VerbSubtreeSource,
    "ancestor_chain": AncestorChainSource,
    "sentence": SentenceSource,
    "legacy_extractor": LegacyExtractorSource,
}


def build_candidate_sources(
    config: CandidateSourcesConfig,
) -> list[CandidateSource]:
    """Instantiate enabled candidate sources in config order."""
    return [CANDIDATE_SOURCES[name]() for name in config.enabled_sources]

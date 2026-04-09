"""Configuration value objects for the fragment selection pipeline.

All values are frozen dataclasses so the config can be safely shared across
use case instances and tweaked via ``dataclasses.replace``.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoringConfig:
    """Weights and thresholds for the default scorer."""

    length_hard_cap_content_words: int = 25
    weight_unknown: int = 1
    weight_length_penalty: int = 1
    weight_content_count: int = 1


@dataclass(frozen=True)
class CleanupConfig:
    """Boundary cleanup settings: enabled rules, pos/dep/lemma tables."""

    min_fragment_content_words: int = 5
    keep_right_punct: frozenset[str] = frozenset({".", "!", "?"})
    enabled_rules: tuple[str, ...] = (
        "punctuation",
        "left_cconj_sconj",
        "left_relativizer",
        "right_cconj_sconj_det_intj",
        "right_dangling_adp",
        "right_dangling_subject_pronoun",
        "right_relative_pronoun",
        "right_possessive_pronoun",
        "right_dangling_aux_part",
    )
    left_strip_pos: frozenset[str] = frozenset({"CCONJ", "SCONJ"})
    right_strip_pos: frozenset[str] = frozenset(
        {"CCONJ", "SCONJ", "DET", "INTJ"}
    )
    aux_deps: frozenset[str] = frozenset({"aux", "auxpass"})
    subject_deps: frozenset[str] = frozenset({"nsubj", "nsubjpass"})
    right_strip_pron_lemmas: frozenset[str] = frozenset(
        {"i", "you", "he", "she", "it", "we", "they"}
    )
    left_strip_relativizers: frozenset[str] = frozenset(
        {"that", "which", "who", "whom", "whose"}
    )


@dataclass(frozen=True)
class CandidateSourcesConfig:
    """Which candidate sources are enabled, in iteration order."""

    enabled_sources: tuple[str, ...] = (
        "verb_subtree",
        "ancestor_chain",
        "sentence",
        "legacy_extractor",
    )


@dataclass(frozen=True)
class FragmentSelectionConfig:
    """Root config for the fragment selection pipeline."""

    sources: CandidateSourcesConfig = field(default_factory=CandidateSourcesConfig)
    cleanup: CleanupConfig = field(default_factory=CleanupConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    fallback_to_cleaned_legacy: bool = True

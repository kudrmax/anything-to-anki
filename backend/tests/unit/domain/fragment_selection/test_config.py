import dataclasses

from backend.domain.value_objects.fragment_selection_config import (
    CandidateSourcesConfig,
    CleanupConfig,
    FragmentSelectionConfig,
    ScoringConfig,
)


def test_default_config_mirrors_current_behavior() -> None:
    cfg = FragmentSelectionConfig()
    assert cfg.scoring.length_hard_cap_content_words == 25
    assert cfg.cleanup.min_fragment_content_words == 5
    assert cfg.cleanup.keep_right_punct == frozenset({".", "!", "?"})
    assert "verb_subtree" in cfg.sources.enabled_sources
    assert "legacy_extractor" in cfg.sources.enabled_sources
    assert cfg.fallback_to_cleaned_legacy is True


def test_config_is_frozen() -> None:
    cfg = ScoringConfig()
    try:
        cfg.length_hard_cap_content_words = 10  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ScoringConfig is not frozen")


def test_replace_disables_rule() -> None:
    cfg = FragmentSelectionConfig()
    new_cleanup = dataclasses.replace(
        cfg.cleanup,
        enabled_rules=tuple(
            r for r in cfg.cleanup.enabled_rules if r != "punctuation"
        ),
    )
    new_cfg = dataclasses.replace(cfg, cleanup=new_cleanup)
    assert "punctuation" not in new_cfg.cleanup.enabled_rules
    assert "punctuation" in cfg.cleanup.enabled_rules  # original untouched


def test_all_default_strip_rules_are_named() -> None:
    expected = {
        "punctuation",
        "left_cconj_sconj",
        "left_relativizer",
        "right_cconj_sconj_det_intj",
        "right_dangling_adp",
        "right_dangling_subject_pronoun",
        "right_relative_pronoun",
        "right_possessive_pronoun",
        "right_dangling_aux_part",
    }
    assert set(CleanupConfig().enabled_rules) == expected


def test_candidate_sources_defaults() -> None:
    assert CandidateSourcesConfig().enabled_sources == (
        "verb_subtree",
        "ancestor_chain",
        "sentence",
        "legacy_extractor",
    )

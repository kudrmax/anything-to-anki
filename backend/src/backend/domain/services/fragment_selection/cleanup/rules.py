"""Strip rules applied to fragment edges by the BoundaryCleaner.

Each rule is a class implementing the ``StripRule`` protocol. Rules are
registered by string name in ``registry.py`` and selected per-config via
``CleanupConfig.enabled_rules``.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Protocol

from backend.domain.services.fragment_selection.utils import count_content_words

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.value_objects.fragment_selection_config import CleanupConfig


class Edge(Enum):
    """Which edge of a fragment a strip rule is asked about."""

    LEFT = "left"
    RIGHT = "right"


class StripRule(Protocol):
    """A rule that decides whether the edge token should be stripped."""

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        ...


_RELATIVIZER_POS: frozenset[str] = frozenset({"PRON", "SCONJ", "DET", "ADV"})
_POSSESSIVE_TAG: str = "PRP$"
_AUX_PART_POS: frozenset[str] = frozenset({"AUX", "PART"})


def _meets_min_after(
    tokens: list[TokenData],
    remaining: list[int],
    config: CleanupConfig,
) -> bool:
    return count_content_words(tokens, remaining) >= config.min_fragment_content_words


class PunctuationRule:
    """Strip a punctuation token at the edge, except sentence-final . ! ?
    on the right."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        idx = indices[0] if edge is Edge.LEFT else indices[-1]
        token = tokens[idx]
        if not token.is_punct:
            return False
        if edge is Edge.RIGHT and token.text in self._config.keep_right_punct:
            return False
        remaining = indices[1:] if edge is Edge.LEFT else indices[:-1]
        return _meets_min_after(tokens, remaining, self._config)


class LeftCconjSconjRule:
    """Strip a coordinator/subordinator at the left edge (``but``, ``and``,
    ``because``)."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.LEFT:
            return False
        token = tokens[indices[0]]
        if token.is_punct:
            return False
        if token.pos not in self._config.left_strip_pos:
            return False
        return _meets_min_after(tokens, indices[1:], self._config)


class LeftRelativizerRule:
    """Strip relativizer/complementizer ``that/which/who/whom/whose`` at the
    left edge. Keep it if the next token is a noun (demonstrative determiner
    like ``that man``, ``which book``)."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.LEFT:
            return False
        token = tokens[indices[0]]
        if token.is_punct:
            return False
        if token.lemma.lower() not in self._config.left_strip_relativizers:
            return False
        if token.pos not in _RELATIVIZER_POS:
            return False
        if len(indices) >= 2:
            next_token = tokens[indices[1]]
            if next_token.pos in {"NOUN", "PROPN"}:
                return False
        return _meets_min_after(tokens, indices[1:], self._config)


class RightCconjSconjDetIntjRule:
    """Strip trailing CCONJ/SCONJ/DET/INTJ at the right edge."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.RIGHT:
            return False
        token = tokens[indices[-1]]
        if token.is_punct:
            return False
        if token.pos not in self._config.right_strip_pos:
            return False
        return _meets_min_after(tokens, indices[:-1], self._config)


class RightDanglingAdpRule:
    """Strip a trailing adposition whose object is not in the fragment."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.RIGHT:
            return False
        token = tokens[indices[-1]]
        if token.pos != "ADP":
            return False
        index_set = set(indices)
        has_object_inside = any(
            child in index_set for child in token.children_indices
        )
        if has_object_inside:
            return False
        return _meets_min_after(tokens, indices[:-1], self._config)


class RightDanglingSubjectPronounRule:
    """Strip a dangling subject pronoun at the right edge whose verb head
    is outside the fragment (e.g. ``...and she`` without a verb)."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.RIGHT:
            return False
        token = tokens[indices[-1]]
        if token.pos != "PRON":
            return False
        if token.lemma.lower() not in self._config.right_strip_pron_lemmas:
            return False
        if token.dep not in self._config.subject_deps:
            return False
        if token.head_index in indices:
            return False
        return _meets_min_after(tokens, indices[:-1], self._config)


class RightRelativePronounRule:
    """Strip a dangling relative/demonstrative pronoun at the right edge
    (``...i.e., that``)."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.RIGHT:
            return False
        token = tokens[indices[-1]]
        if token.pos != "PRON":
            return False
        if token.lemma.lower() not in self._config.left_strip_relativizers:
            return False
        return _meets_min_after(tokens, indices[:-1], self._config)


class RightPossessivePronounRule:
    """Strip a trailing possessive pronoun (``hit its`` expects a noun)."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.RIGHT:
            return False
        token = tokens[indices[-1]]
        if token.pos != "PRON":
            return False
        if token.tag != _POSSESSIVE_TAG:
            return False
        return _meets_min_after(tokens, indices[:-1], self._config)


class RightDanglingAuxPartRule:
    """Strip a trailing aux/particle whose head verb is outside the
    fragment (``...considered to have``)."""

    def __init__(self, config: CleanupConfig) -> None:
        self._config = config

    def applies(
        self,
        tokens: list[TokenData],
        indices: list[int],
        edge: Edge,
    ) -> bool:
        if edge is not Edge.RIGHT:
            return False
        token = tokens[indices[-1]]
        if token.pos not in _AUX_PART_POS:
            return False
        if token.dep not in self._config.aux_deps:
            return False
        if token.head_index in indices:
            return False
        return _meets_min_after(tokens, indices[:-1], self._config)

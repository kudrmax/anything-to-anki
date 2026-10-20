from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.domain.value_objects.number_format import NumberFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.collection_choice import CollectionChoice
    from backend.domain.value_objects.naming_rule import NamingRule


@dataclass(frozen=True)
class Naming:
    """How the user named the sources of one add: their collection, the rule, and the rows
    rewritten by hand, by row index."""

    collection: CollectionChoice
    rule: NamingRule
    titles: Mapping[int, str] = field(default_factory=dict)
    number_format: NumberFormat = field(default_factory=NumberFormat)

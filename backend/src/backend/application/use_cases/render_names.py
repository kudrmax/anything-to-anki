from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.naming_rule import NamingRule
from backend.domain.value_objects.number_format import NumberFormat

if TYPE_CHECKING:
    from collections.abc import Sequence


class RenderNamesUseCase:
    """The titles a rule gives the sources of one add, in order; for the naming window."""

    def execute(
        self,
        rule: str,
        collection_name: str | None,
        own_titles: Sequence[str],
        digits: int | None = None,
    ) -> list[str]:
        naming_rule = NamingRule(rule)
        width = NumberFormat(digits).width(len(own_titles))
        return [
            naming_rule.render(collection_name, number, own_title, width)
            for number, own_title in enumerate(own_titles, start=1)
        ]

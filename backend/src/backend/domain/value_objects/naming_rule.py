from __future__ import annotations

from dataclasses import dataclass

COLLECTION_PLACEHOLDER = "{{collection}}"
NUMBER_PLACEHOLDER = "{{n}}"
TITLE_PLACEHOLDER = "{{title}}"
DEFAULT_NAMING_RULE = f"{COLLECTION_PLACEHOLDER} ch{NUMBER_PLACEHOLDER}"
# Without one of these every source of a group would get the same title.
DISTINGUISHING_PLACEHOLDERS: tuple[str, ...] = (NUMBER_PLACEHOLDER, TITLE_PLACEHOLDER)


@dataclass(frozen=True)
class NamingRule:
    """How the sources of one add are titled, e.g. `{{collection}} ch{{n}}`."""

    pattern: str

    def __post_init__(self) -> None:
        if not any(placeholder in self.pattern for placeholder in DISTINGUISHING_PLACEHOLDERS):
            msg = f"Titles must contain {NUMBER_PLACEHOLDER} or {TITLE_PLACEHOLDER}"
            raise ValueError(msg)

    def render(self, collection: str | None, number: int, own_title: str) -> str:
        title = (
            self.pattern.replace(COLLECTION_PLACEHOLDER, collection or "")
            .replace(NUMBER_PLACEHOLDER, str(number))
            .replace(TITLE_PLACEHOLDER, own_title)
        )
        return " ".join(title.split())

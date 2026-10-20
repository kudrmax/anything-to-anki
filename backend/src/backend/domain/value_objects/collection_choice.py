from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CollectionChoice:
    """Where the sources of one add go: an existing collection, a new one, or none."""

    existing_id: int | None = None
    new_name: str | None = None

    def __post_init__(self) -> None:
        if self.existing_id is not None and self.new_name is not None:
            msg = "A collection is either existing or new"
            raise ValueError(msg)
        if self.new_name is not None and not self.new_name.strip():
            msg = "A new collection needs a name"
            raise ValueError(msg)

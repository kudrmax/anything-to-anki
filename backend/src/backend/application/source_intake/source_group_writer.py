from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.dto.add_source_dtos import SourcesCreated
from backend.domain.entities.collection import Collection
from backend.domain.services.collection_tree import CollectionTree
from backend.domain.value_objects.collection_choice import CollectionChoice

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.source_intake.source_draft import SourceDraft
    from backend.application.source_intake.source_writer import SourceWriter
    from backend.domain.ports.collection_repository import CollectionRepository

logger = logging.getLogger(__name__)


class SourceGroupWriter:
    """Stores drafts as sources: one as it is, several titled and gathered together."""

    def __init__(self, writer: SourceWriter, collection_repo: CollectionRepository) -> None:
        self._writer = writer
        self._collection_repo = collection_repo

    def write_one(self, draft: SourceDraft, title: str | None) -> SourcesCreated:
        source_id = self._write(draft, title or draft.own_title, None, None)
        logger.info("Created %s source id=%s from %s", draft.kind, source_id, draft.label)
        return SourcesCreated(source_ids=[source_id])

    def write_group(
        self,
        drafts: Sequence[SourceDraft],
        collection: CollectionChoice,
        titles: Sequence[str],
    ) -> SourcesCreated:
        collection_id = self._collection_id(collection)
        # Added at one moment, the group keeps its order in the newest-first list.
        added_at = datetime.now(tz=UTC)
        source_ids = [
            self._write(draft, title, collection_id, added_at)
            for draft, title in zip(drafts, titles, strict=True)
        ]
        logger.info("Created %d sources in collection id=%s", len(source_ids), collection_id)
        return SourcesCreated(source_ids=source_ids, collection_id=collection_id)

    def resolve(self, name: str) -> CollectionChoice:
        """A top-level collection of this name, or a new one."""
        existing = CollectionTree(self._collection_repo.list_all()).find_top_level(name)
        if existing is not None:
            return CollectionChoice(existing_id=existing.id)
        return CollectionChoice(new_name=name.strip())

    def name_of(self, choice: CollectionChoice) -> str | None:
        if choice.new_name is not None:
            return choice.new_name.strip()
        if choice.existing_id is None:
            return None
        collection = self._collection_repo.get_by_id(choice.existing_id)
        return collection.name if collection else None

    def _collection_id(self, choice: CollectionChoice) -> int | None:
        if choice.new_name is not None:
            choice = self.resolve(choice.new_name)
        if choice.existing_id is not None:
            return choice.existing_id
        if choice.new_name is None:
            return None
        tree = CollectionTree(self._collection_repo.list_all())
        created = self._collection_repo.create(
            Collection(name=choice.new_name, position=tree.next_position(None)),
        )
        assert created.id is not None
        return created.id

    def _write(
        self,
        draft: SourceDraft,
        title: str | None,
        collection_id: int | None,
        created_at: datetime | None,
    ) -> int:
        return self._writer.write(
            document=draft.document,
            title=title,
            source_format=draft.source_format,
            kind=draft.kind,
            video=draft.video,
            collection_id=collection_id,
            created_at=created_at,
        )

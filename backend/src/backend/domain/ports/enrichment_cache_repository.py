from __future__ import annotations

from abc import ABC, abstractmethod


class EnrichmentCacheRepository(ABC):
    """Port for caching and restoring enrichment data during source reprocessing."""

    @abstractmethod
    def save_from_source(self, source_id: int) -> None:
        """Copy enrichment of all candidates for source_id into the cache.

        Matching criteria: (lemma, pos, context_fragment) — bytewise match.
        On duplicate key: ON CONFLICT REPLACE.
        """

    @abstractmethod
    def restore_to_candidates(self, source_id: int) -> int:
        """Restore enrichment for candidates whose (lemma, pos, context_fragment) match cache.

        Restores: meaning, media, pronunciation, TTS.
        Media: uses INSERT OR REPLACE (overwrites pipeline-inserted timecode-only rows).
        Returns number of candidates that had at least one enrichment restored.
        """

    @abstractmethod
    def cleanup(self, source_id: int) -> None:
        """Delete cache entries for source_id."""

    @abstractmethod
    def cleanup_all(self) -> None:
        """Delete all cache entries (for reconcile at startup)."""

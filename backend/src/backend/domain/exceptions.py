class DomainError(Exception):
    """Base class for domain exceptions."""


class TextTooShortError(DomainError):
    """Raised when the input text is too short to analyze."""

    def __init__(self, min_length: int = 1) -> None:
        super().__init__(f"Text must contain at least {min_length} character(s)")
        self.min_length = min_length


class SourceNotFoundError(DomainError):
    """Raised when a source is not found by ID."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source not found: {source_id}")
        self.source_id = source_id


class CandidateNotFoundError(DomainError):
    """Raised when a candidate is not found by ID."""

    def __init__(self, candidate_id: int) -> None:
        super().__init__(f"Candidate not found: {candidate_id}")
        self.candidate_id = candidate_id


class KnownWordNotFoundError(DomainError):
    """Raised when a known word entry is not found by ID."""

    def __init__(self, known_word_id: int) -> None:
        super().__init__(f"Known word not found: {known_word_id}")
        self.known_word_id = known_word_id


class SourceAlreadyProcessedError(DomainError):
    """Raised when trying to process a source that is not in NEW or ERROR status."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source already processed or processing: {source_id}")
        self.source_id = source_id


class InvalidCandidateStatusError(DomainError):
    """Raised when an invalid candidate status is provided."""

    def __init__(self, status: str) -> None:
        super().__init__(f"Invalid candidate status: {status}")
        self.status_value = status


class AnkiNotAvailableError(DomainError):
    """Raised when AnkiConnect is not reachable."""

    def __init__(self) -> None:
        super().__init__("AnkiConnect is not available. Make sure Anki is running with the AnkiConnect plugin.")


class AnkiSyncError(DomainError):
    """Raised when an Anki sync operation fails unexpectedly."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Anki sync failed: {detail}")
        self.detail = detail

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


class EmptyReportCommentError(DomainError):
    """Raised when a complaint about a card has neither a reason nor a comment."""

    def __init__(self) -> None:
        super().__init__("Report has no reason and no comment")


class UnknownReportReasonError(DomainError):
    """Raised when a complaint names a quick reason that is not offered."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Unknown report reason: {reason}")


class KnownWordNotFoundError(DomainError):
    """Raised when a known word entry is not found by ID."""

    def __init__(self, known_word_id: int) -> None:
        super().__init__(f"Known word not found: {known_word_id}")
        self.known_word_id = known_word_id


class SourceIsProcessingError(DomainError):
    """Raised when trying to delete a source that is currently being processed."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source is currently being processed: {source_id}")
        self.source_id = source_id


class SourceAlreadyProcessedError(DomainError):
    """Raised when trying to process a source that is not in NEW or ERROR status."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source already processed or processing: {source_id}")
        self.source_id = source_id


class SourceNotReprocessableError(DomainError):
    """Raised when trying to reprocess a source that is not in a reprocessable status."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source cannot be reprocessed (wrong status): {source_id}")
        self.source_id = source_id


class SourceHasActiveJobsError(DomainError):
    """Raised when trying to reprocess a source that has active enrichment jobs."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source has active enrichment jobs: {source_id}")
        self.source_id = source_id


class InvalidCandidateStatusError(DomainError):
    """Raised when an invalid candidate status is provided."""

    def __init__(self, status: str) -> None:
        super().__init__(f"Invalid candidate status: {status}")
        self.status_value = status


class AnkiNotAvailableError(DomainError):
    """Raised when AnkiConnect is not reachable."""

    def __init__(self) -> None:
        super().__init__(
            "AnkiConnect is not available. Make sure Anki is running with the AnkiConnect plugin."
        )


class AnkiSyncError(DomainError):
    """Raised when an Anki sync operation fails unexpectedly."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Anki sync failed: {detail}")
        self.detail = detail


class AIServiceError(DomainError):
    """Raised when the AI service fails (not authenticated, rate-limited, etc.)."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"AI service error: {detail}")
        self.detail = detail


class GenerationAlreadyRunningError(DomainError):
    """Raised when trying to start generation while one is already running."""

    def __init__(self) -> None:
        super().__init__("A generation job is already running or pending")


class NoActiveCandidatesError(DomainError):
    """Raised when trying to start generation but no active candidates without meaning exist."""

    def __init__(self) -> None:
        super().__init__("No active candidates without meaning to process")


class PermanentError(Exception):
    """Base class for errors that should NOT be retried.

    Use case catches subclasses and writes status=FAILED; worker considers
    the job completed successfully (no retry)."""


class PermanentMediaError(PermanentError):
    """Permanent failure in media extraction."""


class InvalidTimecodesError(PermanentMediaError):
    pass


class BadVideoFormatError(PermanentMediaError):
    pass


class FragmentNotInSrtError(PermanentMediaError):
    pass


class PermanentAIError(PermanentError):
    """Permanent failure in AI generation."""


class ConfigError(DomainError):
    """Raised when application configuration is missing or invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Config error: {detail}")
        self.detail = detail


class SubtitlesNotAvailableError(Exception):
    """Raised when a URL source has no subtitles available."""


class UnsupportedUrlError(Exception):
    """Raised when no fetcher can handle the given URL."""


class CancelledByUserError(Exception):
    """Raised when finished work belongs to jobs no longer running: the user
    cancelled them, or they already failed by timeout. Its result is dropped."""

    def __init__(self, job_ids: list[int]) -> None:
        self.job_ids = job_ids
        super().__init__(f"Jobs {job_ids} are no longer running, result dropped")


class CollectionNotFoundError(DomainError):
    """Raised when a collection is not found by ID."""

    def __init__(self, collection_id: int) -> None:
        super().__init__(f"Collection not found: {collection_id}")
        self.collection_id = collection_id


class CollectionNameExistsError(DomainError):
    """Raised when a collection name is already taken."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Collection name already exists: {name}")
        self.name = name


class SourceNotTopicError(DomainError):
    """Raised when a topic-only operation is requested for a regular source."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source is not a topic: {source_id}")


class TopicTargetsAlreadyGeneratedError(DomainError):
    """Raised when targets are requested for a topic that already has them."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Topic targets already generated: {source_id}")


class TopicTargetsMissingError(DomainError):
    """Raised when a topic is processed before its targets are generated."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Generate topic targets before processing: {source_id}")


class PhrasePolishNotSupportedError(DomainError):
    """Raised when phrases of a source must stay as they are in the source (video)."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Phrases of this source can't be polished: {source_id}")
        self.source_id = source_id


class CandidateNotPolishedError(DomainError):
    """Raised when reverting a polish of a phrase AI never changed."""

    def __init__(self, candidate_id: int) -> None:
        super().__init__(f"Phrase of candidate {candidate_id} is not polished")
        self.candidate_id = candidate_id


class PermanentSourceError(DomainError):
    """Raised when deleting or reprocessing a built-in source the app always keeps."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Built-in source can't be deleted or reprocessed: {source_id}")
        self.source_id = source_id


class InvalidPhraseError(DomainError):
    """Raised when a phrase added by hand is empty or does not contain its target."""


class GenerationNotSupportedError(DomainError):
    """Raised when a source has no use for a kind of generation (e.g. TTS for a video)."""

    def __init__(self, source_id: int, kind: str) -> None:
        super().__init__(f"Source {source_id} doesn't support {kind} generation")
        self.source_id = source_id
        self.kind = kind


class GenerationBlockedError(DomainError):
    """Raised when a kind of generation needs something the source doesn't have yet."""

    def __init__(self, source_id: int, reason: str) -> None:
        super().__init__(f"Generation for source {source_id} is blocked: {reason}")
        self.source_id = source_id
        self.reason = reason



class ImageSearchError(DomainError):
    """Raised when a picture source can't be reached or answers with garbage."""


class UnknownImageUrlError(DomainError):
    """Raised when asked to download a picture no picture source handed out."""

    def __init__(self, url: str) -> None:
        super().__init__(f"Picture URL doesn't come from a known source: {url}")
        self.url = url


class SourceHasNoUrlError(DomainError):
    """Raised when a source-URL operation is requested for a source without a URL."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source {source_id} has no URL")
        self.source_id = source_id


class VideoAlreadyDownloadedError(DomainError):
    """Raised when a video download is requested for a source that already has its video."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Video of source {source_id} is already downloaded")
        self.source_id = source_id


class InvalidClozeError(DomainError, ValueError):
    """Raised when the hidden words of a cloze card are empty or out of the phrase."""


class ClozeNotAllowedError(DomainError):
    """Raised when a cloze card is requested for a candidate that cannot have one."""


class ClozePhraseChangedError(DomainError):
    """Raised when the cloze markup was made for a phrase the card no longer shows."""

    def __init__(self, candidate_id: int) -> None:
        super().__init__(f"Phrase of candidate {candidate_id} changed, mark the words again")
        self.candidate_id = candidate_id

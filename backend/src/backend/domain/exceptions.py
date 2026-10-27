from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.card_choice import Refusal


class DomainError(Exception):
    """Base class for domain exceptions."""


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
    """Raised when a known word entry is not found by its ID or removal key."""

    def __init__(self, known_word_id: int | str) -> None:
        super().__init__(f"Known word not found: {known_word_id}")
        self.known_word_id = known_word_id


class KnownRemovalLeftKnownError(DomainError):
    """The Known removal ran before an Unknown mark and the lemma still reads Known: a rule
    gap, not a state to mark over."""

    def __init__(self, lemma: str) -> None:
        super().__init__(f"Known removal left the lemma Known: {lemma}")
        self.lemma = lemma


class SourceIsProcessingError(DomainError):
    """Raised when trying to delete a source a long operation (processing, rebuild) holds."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source is currently being processed: {source_id}")
        self.source_id = source_id


class SourceAlreadyProcessedError(DomainError):
    """Raised when trying to process a source that is not in NEW or ERROR status."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source already processed or processing: {source_id}")
        self.source_id = source_id


class SourceOperationBusyError(DomainError):
    """Raised when a source is held by another long operation (processing, rebuild)."""

    def __init__(self, source_id: int, kind: str | None = None) -> None:
        busy_with = f" ({kind})" if kind else ""
        super().__init__(f"Source is busy with another operation{busy_with}: {source_id}")
        self.source_id = source_id
        self.kind = kind


class LongOperationInProgressError(DomainError):
    """Raised by a write while a long operation runs: nothing else changes meanwhile."""

    def __init__(self) -> None:
        super().__init__("A long operation is running")


class LongOperationRunningError(DomainError):
    """Raised by a long operation started while a preview or the index build runs."""

    def __init__(self) -> None:
        super().__init__("Wait for the running operation to finish")


class LongOperationCancelledError(DomainError):
    """Raised inside a long operation the user cancelled: it is rolled back."""

    def __init__(self) -> None:
        super().__init__("The operation was cancelled")


class RebuildNotSupportedError(DomainError):
    """Raised when the source offers no rebuild (it was never processed), or no source of
    the set does."""

    def __init__(self, source_id: int | None = None, *, scope: str | None = None) -> None:
        if source_id is None:
            super().__init__(f"No source of the set can be rebuilt: {scope}")
        else:
            super().__init__(
                f"Only a processed source with its own text can be rebuilt: {source_id}",
            )
        self.source_id = source_id
        self.scope = scope


class RefreshNotSupportedError(DomainError):
    """Raised when refreshing a source that is not a processed topic, or a set without one."""

    def __init__(self, source_id: int | None = None, *, scope: str | None = None) -> None:
        if source_id is None:
            super().__init__(f"No topic of the set can be refreshed: {scope}")
        else:
            super().__init__(f"Only a processed topic can be refreshed: {source_id}")
        self.source_id = source_id
        self.scope = scope


class AnkiNotAvailableError(DomainError):
    """Raised when AnkiConnect is not reachable."""

    def __init__(self) -> None:
        super().__init__(
            "AnkiConnect is not available. Make sure Anki is running with the AnkiConnect plugin."
        )


class AnkiNoteTypeIncompleteError(DomainError):
    """Raised when a note type lacks fields the export fills: Anki would drop them silently."""

    def __init__(self, note_type: str, missing_fields: list[str], exists: bool) -> None:
        problem = (
            f"lacks the fields {', '.join(missing_fields)}"
            if exists
            else "is not in Anki"
        )
        fix = "Add missing fields" if exists else "Create note type"
        super().__init__(
            f"Note type «{note_type}» {problem}. Nothing was exported: these parts of "
            f"the cards would be lost. Fix it in Settings → Anki → {fix}."
        )
        self.note_type = note_type
        self.missing_fields = missing_fields


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


class AIUnavailableError(AIServiceError):
    """Raised when the AI can answer no request now (no login, proxy down, blocked country).

    Nothing is wrong with the request itself: the same one succeeds once the AI is back."""


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
    cancelled them, or they already failed by timeout. Its result is dropped, except what
    it wrote while they still ran: `wrote` tells whether there is any."""

    def __init__(self, job_ids: list[int], wrote: bool = False) -> None:
        self.job_ids = job_ids
        self.wrote = wrote
        outcome = "what was written before that stays" if wrote else "result dropped"
        super().__init__(f"Jobs {job_ids} are no longer running, {outcome}")


class CollectionNotFoundError(DomainError):
    """Raised when a collection is not found by ID."""

    def __init__(self, collection_id: int) -> None:
        super().__init__(f"Collection not found: {collection_id}")
        self.collection_id = collection_id


class ScopeNotReviewableError(DomainError):
    """Raised when a set of sources that is not for review is opened for review."""

    def __init__(self, kind: str) -> None:
        super().__init__(f"Scope is not for review: {kind}")
        self.kind = kind


class CollectionNameExistsError(DomainError):
    """Raised when a sibling collection already has this name."""

    def __init__(self, name: str) -> None:
        super().__init__(f'Collection "{name}" already exists here')
        self.name = name


class CollectionMoveNotAllowedError(DomainError):
    """Raised when a collection would end up deeper than the depth limit or inside itself."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class BookReadError(DomainError):
    """Raised when a book file can't be read."""


class NotATextFileError(DomainError):
    """Raised when a file meant to be read as text is binary."""

    def __init__(self, path: str) -> None:
        super().__init__(f"Not a text file: {path}")
        self.path = path


class SourceHasNoDocumentError(DomainError):
    """Raised when a source that should have a document has none."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source {source_id} has no document")
        self.source_id = source_id


class SourceDocumentExistsError(DomainError):
    """Raised when a source's document would be written again: it is written once, with the
    source, and never changes."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Source {source_id} already has a document")
        self.source_id = source_id


class TextBlockNotFoundError(DomainError):
    """Raised when a block asked for is not in the document."""

    def __init__(self, block: int) -> None:
        super().__init__(f"No block {block} in the document")
        self.block = block


class InvalidSourceInputError(DomainError):
    """Raised when an input can't become a source: nothing to read, or a wrong combination."""


class InvalidAnswerError(DomainError):
    """Raised when an answer names a question that wasn't asked or an option it doesn't have."""


class InputFailedError(DomainError):
    """Raised when one input of several added at once can't be read; nothing is added."""

    def __init__(self, label: str, cause: Exception) -> None:
        super().__init__(f"{label}: {cause}")
        self.label = label
        self.cause = cause


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
    """Raised when deleting a built-in source the app always keeps."""

    def __init__(self, source_id: int) -> None:
        super().__init__(f"Built-in source can't be deleted: {source_id}")
        self.source_id = source_id


class InvalidPhraseError(DomainError):
    """Raised when a phrase added by hand is empty or does not contain its target."""


class TargetNotInPhraseError(InvalidPhraseError):
    """Raised when the target is not among the words of a phrase's text."""

    def __init__(self, message: str = "Target is missing from the phrase") -> None:
        super().__init__(message)


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


class PhraseNotFoundError(DomainError):
    """Raised when a phrase (an occurrence of a word) does not exist."""

    def __init__(self, phrase_id: int) -> None:
        super().__init__(f"Phrase {phrase_id} not found")
        self.phrase_id = phrase_id


class ReviewNotFoundError(DomainError):
    """Raised when an open review is not held: never opened, or let go since (a restart, or
    newer reviews pushed it out)."""

    def __init__(self, review_id: str) -> None:
        super().__init__(f"Review {review_id} is not open")
        self.review_id = review_id


class ActionRefusedError(DomainError):
    """Raised when the decision table refuses a button on a card. `reason`: why, for the
    person who pressed it."""

    def __init__(self, card_id: int, refusal: Refusal, reason: str | None = None) -> None:
        super().__init__(reason or f"Card {card_id}: {refusal.value}")
        self.card_id = card_id
        self.refusal = refusal


class NoDecisionRuleError(DomainError):
    """Raised when no row of a decision table matches: the state is impossible, a bug."""

    def __init__(self, key: object) -> None:
        super().__init__(f"No decision rule for {key!r}")
        self.key = key


class PhraseChangedError(DomainError):
    """Raised when a phrase changed or went while something was being made for it."""

    def __init__(self, phrase_id: int) -> None:
        super().__init__(f"Phrase {phrase_id} changed meanwhile, try again")
        self.phrase_id = phrase_id


class PhraseSectionMissingError(DomainError):
    """Raised when a stored phrase has no section, which every phrase must have."""

    def __init__(self, phrase_id: int) -> None:
        super().__init__(f"Phrase {phrase_id} has no section")
        self.phrase_id = phrase_id


class InvalidEarnedSectionError(DomainError):
    """Raised when a phrase is given a section it cannot earn."""

    def __init__(self, section: object) -> None:
        super().__init__(f"A phrase cannot earn the section {section!r}")
        self.section = section


class NestedWriteError(DomainError):
    """Raised when a write transaction is opened inside another one of the same unit of work."""

    def __init__(self) -> None:
        super().__init__("A write transaction is already open: write() cannot be nested")


class WriteInReadError(DomainError):
    """Raised when something is written inside a read transaction, which only reads."""

    def __init__(self) -> None:
        super().__init__("A write was made inside read(): a read transaction only reads")


class UncommittedWorkError(DomainError):
    """Raised when a write transaction opens on a session that holds changes made outside
    any write: they would be committed by a write that does not own them."""

    def __init__(self) -> None:
        super().__init__("Changes were made outside write(): the session has pending work")

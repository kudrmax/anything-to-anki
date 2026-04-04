from backend.application.dto.analysis_dtos import (
    AnalyzeTextRequest,
    AnalyzeTextResponse,
    WordCandidateDTO,
)
from backend.application.dto.candidate_dtos import MarkCandidateRequest
from backend.application.dto.known_word_dtos import KnownWordDTO
from backend.application.dto.settings_dtos import SettingsDTO, UpdateSettingsRequest
from backend.application.dto.source_dtos import (
    CreateSourceRequest,
    SourceDetailDTO,
    SourceDTO,
    StoredCandidateDTO,
)

__all__ = [
    "AnalyzeTextRequest",
    "AnalyzeTextResponse",
    "CreateSourceRequest",
    "KnownWordDTO",
    "MarkCandidateRequest",
    "SettingsDTO",
    "SourceDTO",
    "SourceDetailDTO",
    "StoredCandidateDTO",
    "UpdateSettingsRequest",
    "WordCandidateDTO",
]

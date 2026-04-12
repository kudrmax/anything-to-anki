from __future__ import annotations

from collections.abc import Iterator  # noqa: TC003 — used at runtime by @contextmanager
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.application.use_cases.add_manual_candidate import AddManualCandidateUseCase
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.use_cases.get_source_cards import GetSourceCardsUseCase
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.use_cases.get_stats import GetStatsUseCase
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.use_cases.mark_candidate import MarkCandidateUseCase
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.application.use_cases.rename_source import RenameSourceUseCase
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.domain.value_objects.fragment_selection_config import (
    FragmentSelectionConfig,
)
from backend.domain.value_objects.input_method import InputMethod
from backend.infrastructure.adapters.ai_model_mapping import model_id_for
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector
from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource
from backend.infrastructure.adapters.http_ai_service import HttpAIService
from backend.infrastructure.adapters.json_phrasal_verb_dictionary import (
    JsonPhrasalVerbDictionary,
)
from backend.infrastructure.adapters.regex_lyrics_parser import RegexLyricsParser
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)
from backend.infrastructure.config.prompts_loader import PromptsLoader
from backend.infrastructure.persistence.sqla_anki_sync_repository import (
    SqlaAnkiSyncRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import (
    SqlaSettingsRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)
from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
    from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
    from backend.application.use_cases.create_source_from_url import CreateSourceFromUrlUseCase
    from backend.application.use_cases.download_video import DownloadVideoUseCase
    from backend.application.use_cases.enqueue_meaning_generation import (
        EnqueueMeaningGenerationUseCase,
    )
    from backend.application.use_cases.enqueue_media_generation import (
        EnqueueMediaGenerationUseCase,
    )
    from backend.application.use_cases.get_media_storage_stats import GetMediaStorageStatsUseCase
    from backend.application.use_cases.regenerate_candidate_media import (
        RegenerateCandidateMediaUseCase,
    )
    from backend.application.use_cases.run_media_extraction_job import MediaExtractionUseCase
    from backend.domain.value_objects.prompts_config import PromptsConfig


class Container:
    """Dependency injection container. Single point of assembly for all dependencies."""

    def __init__(self) -> None:
        import os

        from backend.infrastructure.adapters.ffmpeg_media_extractor import FfmpegMediaExtractor
        from backend.infrastructure.adapters.ffmpeg_subtitle_extractor import (
            FfmpegSubtitleExtractor,
        )

        self._text_analyzer = SpaCyTextAnalyzer()
        self._text_cleaner = RegexTextCleaner()
        self._lyrics_parser = RegexLyricsParser(self._text_analyzer)
        self._srt_parser = RegexSrtParser()
        cefr_data_dir = Path(__file__).resolve().parent.parent / "resources" / "cefr"
        cefr_sources: list[CEFRSource] = [
            CefrpyCEFRSource(),
            EFLLexCEFRSource(cefr_data_dir / "efllex.tsv"),
            OxfordCEFRSource(cefr_data_dir / "oxford5000.csv"),
            KellyCEFRSource(cefr_data_dir / "kelly.csv"),
        ]
        self._cefr_classifier = VotingCEFRClassifier(cefr_sources)
        self._frequency_provider = WordfreqFrequencyProvider()
        self._anki_connector = AnkiConnectConnector()
        self._phrasal_verb_dictionary = JsonPhrasalVerbDictionary()
        self._fragment_selection_config = FragmentSelectionConfig()
        self._subtitle_extractor = FfmpegSubtitleExtractor()
        self._media_extractor = FfmpegMediaExtractor()

        from backend.infrastructure.adapters.ytdlp_subtitle_fetcher import YtDlpSubtitleFetcher
        from backend.infrastructure.adapters.ytdlp_video_downloader import YtDlpVideoDownloader

        self._url_fetchers: list = [YtDlpSubtitleFetcher()]
        self._video_downloader = YtDlpVideoDownloader()
        self._videos_dir = os.path.join(os.getenv("DATA_DIR", "."), "videos")

        self._media_root = os.environ.get(
            "MEDIA_ROOT",
            os.path.join(os.getenv("DATA_DIR", "."), "media"),
        )
        prompts_path = Path(
            os.environ.get("PROMPTS_CONFIG_PATH", "config/prompts.yaml")
        )
        self._prompts_config: PromptsConfig = PromptsLoader().load(prompts_path)
        self._lazy_media_reconciler: LazyMediaReconciler | None = None  # lazy init on first call
        # Lazy-created by get_redis_pool()
        self._redis_pool: Any = None  # arq has no type stubs — Any is justified
        # Session factory — lazy-loaded to avoid circular import with api.dependencies
        self._session_factory: sessionmaker[Session] | None = None

    def _get_session_factory(self) -> sessionmaker[Session]:
        """Lazy-load the session factory to avoid circular imports."""
        if self._session_factory is None:
            from backend.infrastructure.api.dependencies import get_session_factory
            self._session_factory = get_session_factory()
        return self._session_factory

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """Context manager for a DB session with auto-commit/rollback.
        Used by worker job functions which don't have FastAPI request scope."""
        factory = self._get_session_factory()
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def add_manual_candidate_use_case(self, session: Session) -> AddManualCandidateUseCase:
        return AddManualCandidateUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
        )

    def analyze_text_use_case(self) -> AnalyzeTextUseCase:
        return AnalyzeTextUseCase(
            text_cleaner=self._text_cleaner,
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
            fragment_selection_config=self._fragment_selection_config,
        )

    def create_source_use_case(self, session: Session) -> CreateSourceUseCase:
        return CreateSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            subtitle_extractor=self._subtitle_extractor,
            audio_track_lister=self._subtitle_extractor,
        )

    def rename_source_use_case(self, session: Session) -> RenameSourceUseCase:
        return RenameSourceUseCase(
            source_repo=SqlaSourceRepository(session),
        )

    def delete_source_use_case(self, session: Session) -> DeleteSourceUseCase:
        return DeleteSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            media_root=self._media_root,
        )

    def get_sources_use_case(self, session: Session) -> GetSourcesUseCase:
        return GetSourcesUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
        )

    def process_source_use_case(self, session: Session) -> ProcessSourceUseCase:
        return ProcessSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            settings_repo=SqlaSettingsRepository(session),
            analyze_text_use_case=self.analyze_text_use_case(),
            source_parsers={
                InputMethod.LYRICS_PASTED: self._lyrics_parser,
                InputMethod.SUBTITLES_FILE: self._srt_parser,
            },
            structured_srt_parser=self._srt_parser,
            media_repo=SqlaCandidateMediaRepository(session),
        )

    def get_candidates_use_case(self, session: Session) -> GetCandidatesUseCase:
        return GetCandidatesUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
        )

    def mark_candidate_use_case(self, session: Session) -> MarkCandidateUseCase:
        return MarkCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def replace_with_example_use_case(self, session: Session) -> ReplaceWithExampleUseCase:
        return ReplaceWithExampleUseCase(
            candidate_repo=SqlaCandidateRepository(session),
        )

    def manage_known_words_use_case(self, session: Session) -> ManageKnownWordsUseCase:
        return ManageKnownWordsUseCase(
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def manage_settings_use_case(self, session: Session) -> ManageSettingsUseCase:
        return ManageSettingsUseCase(
            settings_repo=SqlaSettingsRepository(session),
        )

    def get_anki_status_use_case(self) -> GetAnkiStatusUseCase:
        return GetAnkiStatusUseCase(connector=self._anki_connector)

    def sync_to_anki_use_case(self, session: Session) -> SyncToAnkiUseCase:
        return SyncToAnkiUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            anki_connector=self._anki_connector,
            settings_repo=SqlaSettingsRepository(session),
            anki_sync_repo=SqlaAnkiSyncRepository(session),
        )

    def get_source_cards_use_case(self, session: Session) -> GetSourceCardsUseCase:
        return GetSourceCardsUseCase(
            candidate_repo=SqlaCandidateRepository(session),
        )

    def generate_meaning_use_case(self, session: Session) -> GenerateMeaningUseCase:
        import os

        settings_repo = SqlaSettingsRepository(session)
        ai_model_key = settings_repo.get("ai_model", "sonnet") or "sonnet"
        ai_proxy_url = os.environ["AI_PROXY_URL"]
        ai_service = HttpAIService(url=ai_proxy_url, model=model_id_for(ai_model_key))
        return GenerateMeaningUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            meaning_repo=SqlaCandidateMeaningRepository(session),
            ai_service=ai_service,
            prompts_config=self._prompts_config,
        )

    def meaning_generation_use_case(self, session: Session) -> MeaningGenerationUseCase:
        import os

        settings_repo = SqlaSettingsRepository(session)
        ai_model_key = settings_repo.get("ai_model", "sonnet") or "sonnet"
        ai_proxy_url = os.environ["AI_PROXY_URL"]
        ai_service = HttpAIService(url=ai_proxy_url, model=model_id_for(ai_model_key))
        return MeaningGenerationUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            meaning_repo=SqlaCandidateMeaningRepository(session),
            ai_service=ai_service,
            prompts_config=self._prompts_config,
        )

    def get_stats_use_case(self, session: Session) -> GetStatsUseCase:
        return GetStatsUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def anki_connector(self) -> AnkiConnectConnector:
        return self._anki_connector

    def media_root(self) -> str:
        return self._media_root

    def prompts_config(self) -> PromptsConfig:
        return self._prompts_config

    def lazy_media_reconciler(self) -> LazyMediaReconciler:
        from backend.infrastructure.api.dependencies import get_session_factory
        if self._lazy_media_reconciler is None:
            self._lazy_media_reconciler = LazyMediaReconciler(
                session_factory=get_session_factory(),
                media_root=self._media_root,
            )
        return self._lazy_media_reconciler

    def media_extraction_use_case(self, session: Session) -> MediaExtractionUseCase:
        from backend.application.use_cases.run_media_extraction_job import (
            MediaExtractionUseCase,
        )
        return MediaExtractionUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            media_repo=SqlaCandidateMediaRepository(session),
            source_repo=SqlaSourceRepository(session),
            media_extractor=self._media_extractor,
            media_root=self._media_root,
        )

    def get_media_storage_stats_use_case(self, session: Session) -> GetMediaStorageStatsUseCase:
        from backend.application.use_cases.get_media_storage_stats import (
            GetMediaStorageStatsUseCase,
        )
        return GetMediaStorageStatsUseCase(
            source_repo=SqlaSourceRepository(session),
            media_root=self._media_root,
        )

    def cleanup_media_use_case(self, session: Session) -> CleanupMediaUseCase:
        from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
        return CleanupMediaUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            media_repo=SqlaCandidateMediaRepository(session),  # NEW
            media_root=self._media_root,
        )

    def regenerate_candidate_media_use_case(
        self, session: Session
    ) -> RegenerateCandidateMediaUseCase:
        from backend.application.use_cases.regenerate_candidate_media import (
            RegenerateCandidateMediaUseCase,
        )
        return RegenerateCandidateMediaUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            media_repo=SqlaCandidateMediaRepository(session),  # NEW
            source_repo=SqlaSourceRepository(session),
            structured_srt_parser=self._srt_parser,
            media_extractor=self._media_extractor,
            media_root=self._media_root,
        )

    def create_source_from_url_use_case(self, session: Session) -> CreateSourceFromUrlUseCase:
        from backend.application.use_cases.create_source_from_url import CreateSourceFromUrlUseCase
        return CreateSourceFromUrlUseCase(
            source_repo=SqlaSourceRepository(session),
            fetchers=self._url_fetchers,
        )

    def download_video_use_case(self, session: Session) -> DownloadVideoUseCase:
        from backend.application.use_cases.download_video import DownloadVideoUseCase
        return DownloadVideoUseCase(
            source_repo=SqlaSourceRepository(session),
            video_downloader=self._video_downloader,
            videos_dir=self._videos_dir,
        )

    def cleanup_youtube_video_use_case(self, session: Session) -> CleanupYoutubeVideoUseCase:
        from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
        return CleanupYoutubeVideoUseCase(
            source_repo=SqlaSourceRepository(session),
            media_repo=SqlaCandidateMediaRepository(session),
        )

    def candidate_meaning_repository(self, session: Session) -> SqlaCandidateMeaningRepository:
        return SqlaCandidateMeaningRepository(session)

    def candidate_media_repository(self, session: Session) -> SqlaCandidateMediaRepository:
        return SqlaCandidateMediaRepository(session)

    def enqueue_media_generation_use_case(
        self, session: Session
    ) -> EnqueueMediaGenerationUseCase:
        from backend.application.use_cases.enqueue_media_generation import (
            EnqueueMediaGenerationUseCase,
        )
        return EnqueueMediaGenerationUseCase(
            media_repo=SqlaCandidateMediaRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            source_repo=SqlaSourceRepository(session),
        )

    def enqueue_meaning_generation_use_case(
        self, session: Session
    ) -> EnqueueMeaningGenerationUseCase:
        from backend.application.use_cases.enqueue_meaning_generation import (
            EnqueueMeaningGenerationUseCase,
        )
        return EnqueueMeaningGenerationUseCase(
            meaning_repo=SqlaCandidateMeaningRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            source_repo=SqlaSourceRepository(session),
        )

    async def get_redis_pool(self) -> Any:  # noqa: ANN401 — arq has no type stubs
        """Lazy-init shared ArqRedis pool for enqueueing jobs from FastAPI."""
        import os

        from arq import create_pool
        from arq.connections import RedisSettings

        if self._redis_pool is None:
            self._redis_pool = await create_pool(
                RedisSettings.from_dsn(
                    os.environ.get("REDIS_URL", "redis://localhost:6379")
                )
            )
        return self._redis_pool

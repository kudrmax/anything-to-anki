from __future__ import annotations

import logging
import os
from collections.abc import Iterator  # noqa: TC003 — used at runtime by @contextmanager
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from backend.application.use_cases.add_manual_candidate import AddManualCandidateUseCase
from backend.application.use_cases.add_saved_phrase import AddSavedPhraseUseCase
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.application.use_cases.assign_source_collection import AssignSourceToCollectionUseCase
from backend.application.use_cases.build_bootstrap_index import BuildBootstrapIndexUseCase
from backend.application.use_cases.create_collection import CreateCollectionUseCase
from backend.application.use_cases.create_source import CreateSourceUseCase
from backend.application.use_cases.delete_collection import DeleteCollectionUseCase
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase
from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
from backend.application.use_cases.get_reprocess_stats import GetReprocessStatsUseCase
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.use_cases.get_stats import GetStatsUseCase
from backend.application.use_cases.list_collections import ListCollectionsUseCase
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.use_cases.mark_candidate import MarkCandidateUseCase
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.application.use_cases.rename_collection import RenameCollectionUseCase
from backend.application.use_cases.rename_source import RenameSourceUseCase
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.application.use_cases.report_candidate import ReportCandidateUseCase
from backend.application.use_cases.reprocess_source import ReprocessSourceUseCase
from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
from backend.application.utils.candidate_factory import CandidateFactory
from backend.application.utils.candidate_sorter import CandidateSorter
from backend.application.utils.frequent_word_threshold_resolver import (
    FrequentWordThresholdResolver,
)
from backend.application.utils.review_status_updater import ReviewStatusUpdater
from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
from backend.domain.ports.cefr_source import (
    CEFRSource,  # noqa: TC001 — used at runtime in list[CEFRSource]
)
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.fragment_selection_config import (
    FragmentSelectionConfig,
)
from backend.domain.value_objects.input_method import InputMethod
from backend.infrastructure.adapters.ai_model_mapping import model_id_for
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector
from backend.infrastructure.adapters.bing_image_source import BingImageSource
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.pronunciation_source import (
    DictCachePronunciationSource,
)
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader
from backend.infrastructure.adapters.dict_cache.usage_source import DictCacheUsageSource
from backend.infrastructure.adapters.dict_cache.word_corpus_provider import (
    DictCacheWordCorpusProvider,
)
from backend.infrastructure.adapters.http_ai_service import HttpAIService
from backend.infrastructure.adapters.http_fetch import APP_USER_AGENT, http_get
from backend.infrastructure.adapters.json_phrasal_verb_dictionary import (
    JsonPhrasalVerbDictionary,
)
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
from backend.infrastructure.adapters.pillow_card_picture_encoder import PillowCardPictureEncoder
from backend.infrastructure.adapters.regex_lyrics_parser import RegexLyricsParser
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.throttled_http_file_downloader import (
    ThrottledHttpFileDownloader,
)
from backend.infrastructure.adapters.video_path_resolver import VideoPathResolverImpl
from backend.infrastructure.adapters.wiktionary_image_source import WiktionaryImageSource
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)
from backend.infrastructure.config.prompts_loader import PromptsLoader
from backend.infrastructure.persistence.sqla_anki_sync_repository import (
    SqlaAnkiSyncRepository,
)
from backend.infrastructure.persistence.sqla_bootstrap_index_repository import (
    SqlaBootstrapIndexRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_card_report_repository import (
    SqlaCardReportRepository,
)
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_known_word_repository import (
    SqlaKnownWordRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import (
    SqlaSettingsRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)
from backend.infrastructure.persistence.sqla_word_decision_repository import (
    SqlaWordDecisionRepository,
)
from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
    from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
    from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
    from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
    from backend.application.use_cases.create_source_from_url import CreateSourceFromUrlUseCase
    from backend.application.use_cases.download_pronunciation import DownloadPronunciationUseCase
    from backend.application.use_cases.download_video import DownloadVideoUseCase
    from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
    from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
    from backend.application.use_cases.enqueue_topic_generation import (
        EnqueueTopicGenerationUseCase,
    )
    from backend.application.use_cases.generate_topic_targets import GenerateTopicTargetsUseCase
    from backend.application.use_cases.generate_tts import GenerateTTSUseCase
    from backend.application.use_cases.get_ai_usage_stats import GetAIUsageStatsUseCase
    from backend.application.use_cases.get_generation_status import GetGenerationStatusUseCase
    from backend.application.use_cases.get_media_storage_stats import GetMediaStorageStatsUseCase
    from backend.application.use_cases.get_queue_failed import GetQueueFailedUseCase
    from backend.application.use_cases.get_queue_global_summary import (
        GetQueueGlobalSummaryUseCase,
    )
    from backend.application.use_cases.get_queue_order import GetQueueOrderUseCase
    from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
    from backend.application.use_cases.regenerate_candidate_media import (
        RegenerateCandidateMediaUseCase,
    )
    from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
    from backend.application.use_cases.run_generation import RunGenerationUseCase
    from backend.application.use_cases.run_media_extraction_job import MediaExtractionUseCase
    from backend.application.use_cases.search_target_images import SearchTargetImagesUseCase
    from backend.application.utils.generation_targets import GenerationTarget
    from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
    from backend.domain.ports.target_image_source import TargetImageSource
    from backend.domain.ports.url_source_fetcher import UrlSourceFetcher
    from backend.domain.value_objects.prompts_config import PromptsConfig
    from backend.infrastructure.adapters.kokoro_tts_generator import KokoroTTSGenerator

logger = logging.getLogger(__name__)


class Container:
    """Dependency injection container. Single point of assembly for all dependencies."""

    def __init__(self) -> None:

        from backend.infrastructure.adapters.ffmpeg_media_extractor import FfmpegMediaExtractor
        from backend.infrastructure.adapters.ffmpeg_subtitle_extractor import (
            FfmpegSubtitleExtractor,
        )

        self._text_analyzer = SpaCyTextAnalyzer()
        self._text_cleaner = RegexTextCleaner()
        self._text_normalizer = SlangNormalizer()
        self._lyrics_parser = RegexLyricsParser(self._text_analyzer)
        self._srt_parser = RegexSrtParser()
        project_root = Path(__file__).resolve().parents[4]

        # Dictionary cache — DICTIONARIES_DIR is required
        dictionaries_dir_env = os.environ.get("DICTIONARIES_DIR")
        if not dictionaries_dir_env:
            logger.warning("DICTIONARIES_DIR not set — dictionaries disabled")
            dict_cache_path = Path("/nonexistent")
        else:
            dict_cache_path = Path(dictionaries_dir_env) / ".cache" / "dict.db"

        self._dict_reader = DictCacheReader(dict_cache_path)
        self._word_corpus_provider = DictCacheWordCorpusProvider(self._dict_reader)

        # CEFR: dynamic sources from dict.db metadata
        cefr_sources: list[CEFRSource] = []
        priority_sources: list[CEFRSource] = []
        for meta in self._dict_reader.get_cefr_sources():
            src = DictCacheCEFRSource(self._dict_reader, meta["name"])
            if meta["priority"] == "high":
                priority_sources.append(src)
            else:
                cefr_sources.append(src)
        cefr_sources.append(CefrpyCEFRSource())  # built-in fallback

        self._cefr_classifier = VotingCEFRClassifier(
            cefr_sources,
            priority_sources=priority_sources,
        )

        self._pronunciation_source = DictCachePronunciationSource(self._dict_reader)

        self._tts_generator: KokoroTTSGenerator | None = None
        self._usage_source = DictCacheUsageSource(self._dict_reader)
        self._frequency_provider = WordfreqFrequencyProvider()
        self._anki_connector = AnkiConnectConnector()
        self._file_downloader = ThrottledHttpFileDownloader()
        # Dictionary first: when it has a picture, that picture shows exactly the word.
        self._target_image_sources: list[TargetImageSource] = [
            WiktionaryImageSource(),
            BingImageSource(),
        ]
        # Its own pacing: a picture the user picked must not queue behind bulk
        # pronunciation downloads, nor wait minutes out on a rate limit.
        self._image_downloader = ThrottledHttpFileDownloader(
            retry_delays_s=(),
            fetch=partial(http_get, user_agent=APP_USER_AGENT),
        )
        self._phrasal_verb_dictionary = JsonPhrasalVerbDictionary()
        self._fragment_selection_config = FragmentSelectionConfig()
        self._subtitle_extractor = FfmpegSubtitleExtractor()
        self._picture_encoder = PillowCardPictureEncoder()
        self._media_extractor = FfmpegMediaExtractor(self._picture_encoder)
        self._file_reader = LocalFileReader()

        from backend.infrastructure.adapters.ytdlp_subtitle_fetcher import YtDlpSubtitleFetcher
        from backend.infrastructure.adapters.ytdlp_video_downloader import YtDlpVideoDownloader

        self._url_fetchers: list[UrlSourceFetcher] = [YtDlpSubtitleFetcher()]
        self._video_downloader = YtDlpVideoDownloader()
        data_dir = os.path.abspath(os.getenv("DATA_DIR", "./data"))
        self._video_path_resolver = VideoPathResolverImpl(data_dir=data_dir)

        self._media_root = os.environ.get(
            "MEDIA_ROOT",
            os.path.join(data_dir, "media"),
        )
        default_prompts = project_root / "config" / "prompts.yaml"
        prompts_path = Path(
            os.environ.get("PROMPTS_CONFIG_PATH", str(default_prompts))
        )
        self._prompts_config: PromptsConfig = PromptsLoader().load(prompts_path)
        self._lazy_media_reconciler: LazyMediaReconciler | None = None  # lazy init on first call
        templates_dir = project_root / "anki-templates"
        self._anki_template_renderer = AnkiTemplateRenderer(templates_dir)
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

    def job_repository(self, session: Session) -> SqlaJobRepository:
        return SqlaJobRepository(session)

    def add_manual_candidate_use_case(self, session: Session) -> AddManualCandidateUseCase:
        return AddManualCandidateUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
            review_status=self._review_status_updater(session),
        )

    def add_saved_phrase_use_case(self, session: Session) -> AddSavedPhraseUseCase:
        return AddSavedPhraseUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
            review_status=self._review_status_updater(session),
        )

    def analyze_text_use_case(self) -> AnalyzeTextUseCase:
        return AnalyzeTextUseCase(
            text_cleaner=self._text_cleaner,
            text_normalizer=self._text_normalizer,
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
            fragment_selection_config=self._fragment_selection_config,
            usage_lookup=self._usage_source,
        )

    def create_source_use_case(self, session: Session) -> CreateSourceUseCase:
        return CreateSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            subtitle_extractor=self._subtitle_extractor,
            audio_track_lister=self._subtitle_extractor,
            file_reader=self._file_reader,
            video_path_resolver=self._video_path_resolver,
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
            candidate_sorter=self._candidate_sorter(session),
            job_repo=SqlaJobRepository(session),
            collection_repo=SqlaCollectionRepository(session),
            topic_target_repo=SqlaTopicTargetRepository(session),
            report_repo=SqlaCardReportRepository(session),
        )

    def create_collection_use_case(self, session: Session) -> CreateCollectionUseCase:
        return CreateCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
        )

    def list_collections_use_case(self, session: Session) -> ListCollectionsUseCase:
        return ListCollectionsUseCase(
            collection_repo=SqlaCollectionRepository(session),
            source_repo=SqlaSourceRepository(session),
        )

    def rename_collection_use_case(self, session: Session) -> RenameCollectionUseCase:
        return RenameCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
        )

    def delete_collection_use_case(self, session: Session) -> DeleteCollectionUseCase:
        return DeleteCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
        )

    def assign_source_collection_use_case(
        self, session: Session,
    ) -> AssignSourceToCollectionUseCase:
        return AssignSourceToCollectionUseCase(
            source_repo=SqlaSourceRepository(session),
            collection_repo=SqlaCollectionRepository(session),
        )

    def process_source_use_case(self, session: Session) -> ProcessSourceUseCase:
        return ProcessSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            settings_repo=SqlaSettingsRepository(session),
            threshold_resolver=self._threshold_resolver(session),
            analyze_text_use_case=self.analyze_text_use_case(),
            source_parsers={
                InputMethod.LYRICS_PASTED: self._lyrics_parser,
                InputMethod.SUBTITLES_FILE: self._srt_parser,
            },
            structured_srt_parser=self._srt_parser,
            media_repo=SqlaCandidateMediaRepository(session),
            topic_phrase_collector=self._topic_phrase_collector(session),
        )

    def _candidate_factory(self) -> CandidateFactory:
        return CandidateFactory(
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
        )

    def _topic_phrase_collector(self, session: Session) -> TopicPhraseCollector:
        return TopicPhraseCollector(
            topic_target_repo=SqlaTopicTargetRepository(session),
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            candidate_factory=self._candidate_factory(),
        )

    def enqueue_topic_generation_use_case(
        self, session: Session,
    ) -> EnqueueTopicGenerationUseCase:
        from backend.application.use_cases.enqueue_topic_generation import (
            EnqueueTopicGenerationUseCase,
        )
        return EnqueueTopicGenerationUseCase(
            source_repo=SqlaSourceRepository(session),
            topic_target_repo=SqlaTopicTargetRepository(session),
            job_repo=SqlaJobRepository(session),
        )

    def generate_topic_targets_use_case(self, session: Session) -> GenerateTopicTargetsUseCase:
        from backend.application.use_cases.generate_topic_targets import (
            GenerateTopicTargetsUseCase,
        )
        settings_repo = SqlaSettingsRepository(session)
        return GenerateTopicTargetsUseCase(
            source_repo=SqlaSourceRepository(session),
            topic_target_repo=SqlaTopicTargetRepository(session),
            settings_repo=settings_repo,
            ai_service=self._ai_service(settings_repo),
            prompts_config=self._prompts_config,
        )

    def _ai_service(self, settings_repo: SqlaSettingsRepository) -> HttpAIService:
        from backend.infrastructure.persistence.session_ai_usage_recorder import (
            SessionAIUsageRecorder,
        )
        ai_model_key = settings_repo.get("ai_model", "sonnet") or "sonnet"
        return HttpAIService(
            url=os.environ["AI_PROXY_URL"],
            model=model_id_for(ai_model_key),
            usage_recorder=SessionAIUsageRecorder(self._get_session_factory()),
        )

    def get_ai_usage_stats_use_case(self, session: Session) -> GetAIUsageStatsUseCase:
        from backend.application.use_cases.get_ai_usage_stats import GetAIUsageStatsUseCase
        from backend.infrastructure.persistence.sqla_ai_usage_repository import (
            SqlaAIUsageRepository,
        )
        return GetAIUsageStatsUseCase(usage_repo=SqlaAIUsageRepository(session))

    def reprocess_source_use_case(self, session: Session) -> ReprocessSourceUseCase:
        from backend.infrastructure.persistence.sqla_enrichment_cache_repository import (
            SqlaEnrichmentCacheRepository,
        )
        return ReprocessSourceUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            job_repo=SqlaJobRepository(session),
            process_source_use_case=self.process_source_use_case(session),
            enrichment_cache_repo=SqlaEnrichmentCacheRepository(session),
        )

    def get_reprocess_stats_use_case(self, session: Session) -> GetReprocessStatsUseCase:
        return GetReprocessStatsUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            job_repo=SqlaJobRepository(session),
        )

    def get_candidates_use_case(self, session: Session) -> GetCandidatesUseCase:
        return GetCandidatesUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            candidate_sorter=self._candidate_sorter(session),
            job_repo=SqlaJobRepository(session),
            report_repo=SqlaCardReportRepository(session),
        )

    def report_candidate_use_case(self, session: Session) -> ReportCandidateUseCase:
        return ReportCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            source_repo=SqlaSourceRepository(session),
            report_repo=SqlaCardReportRepository(session),
        )

    def mark_candidate_use_case(self, session: Session) -> MarkCandidateUseCase:
        return MarkCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            decision_repo=SqlaWordDecisionRepository(session),
            review_status=self._review_status_updater(session),
        )

    def replace_with_example_use_case(self, session: Session) -> ReplaceWithExampleUseCase:
        return ReplaceWithExampleUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            review_status=self._review_status_updater(session),
        )

    def _threshold_resolver(self, session: Session) -> FrequentWordThresholdResolver:
        return FrequentWordThresholdResolver(
            settings_repo=SqlaSettingsRepository(session),
            decision_repo=SqlaWordDecisionRepository(session),
        )

    def _candidate_sorter(self, session: Session) -> CandidateSorter:
        return CandidateSorter(
            settings_repo=SqlaSettingsRepository(session),
            threshold_resolver=self._threshold_resolver(session),
        )

    def _review_status_updater(self, session: Session) -> ReviewStatusUpdater:
        return ReviewStatusUpdater(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
        )

    def manage_known_words_use_case(self, session: Session) -> ManageKnownWordsUseCase:
        return ManageKnownWordsUseCase(
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def manage_settings_use_case(self, session: Session) -> ManageSettingsUseCase:
        return ManageSettingsUseCase(
            settings_repo=SqlaSettingsRepository(session),
            threshold_resolver=self._threshold_resolver(session),
        )

    def get_anki_status_use_case(self) -> GetAnkiStatusUseCase:
        return GetAnkiStatusUseCase(connector=self._anki_connector)

    def sync_to_anki_use_case(self, session: Session) -> SyncToAnkiUseCase:
        return SyncToAnkiUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            anki_connector=self._anki_connector,
            settings_repo=SqlaSettingsRepository(session),
            anki_sync_repo=SqlaAnkiSyncRepository(session),
            template_renderer=self._anki_template_renderer,
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def get_export_cards_use_case(self, session: Session) -> GetExportCardsUseCase:
        return GetExportCardsUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            source_repo=SqlaSourceRepository(session),
        )

    def generate_meaning_use_case(self, session: Session) -> GenerateMeaningUseCase:
        return GenerateMeaningUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            meaning_repo=SqlaCandidateMeaningRepository(session),
            ai_service=self._ai_service(SqlaSettingsRepository(session)),
            prompts_config=self._prompts_config,
        )

    def meaning_generation_use_case(self, session: Session) -> MeaningGenerationUseCase:
        return MeaningGenerationUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            meaning_repo=SqlaCandidateMeaningRepository(session),
            ai_service=self._ai_service(SqlaSettingsRepository(session)),
            prompts_config=self._prompts_config,
        )

    def phrase_polish_use_case(self, session: Session) -> PhrasePolishUseCase:
        from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
        settings_repo = SqlaSettingsRepository(session)
        return PhrasePolishUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            source_repo=SqlaSourceRepository(session),
            settings_repo=settings_repo,
            enrichment_reset=self._phrase_enrichment_reset(session),
            ai_service=self._ai_service(settings_repo),
            prompts_config=self._prompts_config,
        )

    def enqueue_phrase_polish_use_case(self, session: Session) -> EnqueuePhrasePolishUseCase:
        from backend.application.use_cases.enqueue_phrase_polish import (
            EnqueuePhrasePolishUseCase,
        )
        return EnqueuePhrasePolishUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            source_repo=SqlaSourceRepository(session),
            job_repo=SqlaJobRepository(session),
        )

    def revert_phrase_polish_use_case(self, session: Session) -> RevertPhrasePolishUseCase:
        from backend.application.use_cases.revert_phrase_polish import (
            RevertPhrasePolishUseCase,
        )
        return RevertPhrasePolishUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            enrichment_reset=self._phrase_enrichment_reset(session),
        )

    def edit_card_phrase_use_case(self, session: Session) -> EditCardPhraseUseCase:
        from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
        return EditCardPhraseUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            enrichment_reset=self._phrase_enrichment_reset(session),
        )

    def _phrase_enrichment_reset(self, session: Session) -> PhraseEnrichmentReset:
        from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
        return PhraseEnrichmentReset(
            meaning_repo=SqlaCandidateMeaningRepository(session),
            tts_repo=SqlaCandidateTTSRepository(session),
        )

    def get_stats_use_case(self, session: Session) -> GetStatsUseCase:
        return GetStatsUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
        )

    def build_bootstrap_index_use_case(self, session: Session) -> BuildBootstrapIndexUseCase:
        return BuildBootstrapIndexUseCase(
            corpus_provider=self._word_corpus_provider,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            index_repo=SqlaBootstrapIndexRepository(session),
            phrasal_verb_dictionary=self._phrasal_verb_dictionary,
        )

    def get_bootstrap_words_use_case(self, session: Session) -> GetBootstrapWordsUseCase:
        return GetBootstrapWordsUseCase(
            index_repo=SqlaBootstrapIndexRepository(session),
            known_word_repo=SqlaKnownWordRepository(session),
            settings_repo=SqlaSettingsRepository(session),
        )

    def anki_connector(self) -> AnkiConnectConnector:
        return self._anki_connector

    def media_root(self) -> str:
        return self._media_root

    @property
    def video_path_resolver(self) -> VideoPathResolverImpl:
        return self._video_path_resolver

    @property
    def tts_generator(self) -> KokoroTTSGenerator:
        if self._tts_generator is None:
            from backend.infrastructure.adapters.kokoro_tts_generator import KokoroTTSGenerator
            self._tts_generator = KokoroTTSGenerator()
        return self._tts_generator

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
            video_path_resolver=self._video_path_resolver,
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
            media_repo=SqlaCandidateMediaRepository(session),
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
            media_repo=SqlaCandidateMediaRepository(session),
            source_repo=SqlaSourceRepository(session),
            structured_srt_parser=self._srt_parser,
            media_extractor=self._media_extractor,
            media_root=self._media_root,
            video_path_resolver=self._video_path_resolver,
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
            video_path_resolver=self._video_path_resolver,
        )

    def cleanup_youtube_video_use_case(self, session: Session) -> CleanupYoutubeVideoUseCase:
        from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
        return CleanupYoutubeVideoUseCase(
            source_repo=SqlaSourceRepository(session),
            media_repo=SqlaCandidateMediaRepository(session),
            job_repo=SqlaJobRepository(session),
            video_path_resolver=self._video_path_resolver,
        )

    def candidate_meaning_repository(self, session: Session) -> SqlaCandidateMeaningRepository:
        return SqlaCandidateMeaningRepository(session)

    def candidate_media_repository(self, session: Session) -> SqlaCandidateMediaRepository:
        return SqlaCandidateMediaRepository(session)

    def anki_template_renderer(self) -> AnkiTemplateRenderer:
        return self._anki_template_renderer

    def candidate_pronunciation_repository(
        self, session: Session,
    ) -> SqlaCandidatePronunciationRepository:
        return SqlaCandidatePronunciationRepository(session)

    def download_pronunciation_use_case(
        self, session: Session,
    ) -> DownloadPronunciationUseCase:
        from backend.application.use_cases.download_pronunciation import (
            DownloadPronunciationUseCase,
        )
        return DownloadPronunciationUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            pronunciation_repo=SqlaCandidatePronunciationRepository(session),
            pronunciation_source=self._pronunciation_source,
            file_downloader=self._file_downloader,
            media_root=self._media_root,
        )

    def search_target_images_use_case(self, session: Session) -> SearchTargetImagesUseCase:
        from backend.application.use_cases.search_target_images import (
            SearchTargetImagesUseCase,
        )
        return SearchTargetImagesUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            image_sources=self._target_image_sources,
        )

    def apply_target_image_use_case(self, session: Session) -> ApplyTargetImageUseCase:
        from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
        return ApplyTargetImageUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            media_repo=SqlaCandidateMediaRepository(session),
            image_sources=self._target_image_sources,
            file_downloader=self._image_downloader,
            picture_encoder=self._picture_encoder,
            media_root=self._media_root,
        )

    def generate_tts_use_case(self, session: Session) -> GenerateTTSUseCase:
        from backend.application.use_cases.generate_tts import GenerateTTSUseCase
        return GenerateTTSUseCase(
            candidate_repo=SqlaCandidateRepository(session),
            tts_repo=SqlaCandidateTTSRepository(session),
            tts_generator=self.tts_generator,
            settings_repo=SqlaSettingsRepository(session),
            media_root=self._media_root,
        )

    def _generation_targets(self, session: Session) -> list[GenerationTarget]:
        from backend.application.utils.generation_targets import (
            MeaningTarget,
            MediaTarget,
            PolishTarget,
            PronunciationTarget,
            TTSTarget,
        )
        return [
            PolishTarget(SqlaCandidateRepository(session)),
            MeaningTarget(SqlaCandidateMeaningRepository(session)),
            MediaTarget(),
            PronunciationTarget(),
            TTSTarget(),
        ]

    def get_generation_status_use_case(self, session: Session) -> GetGenerationStatusUseCase:
        from backend.application.use_cases.get_generation_status import (
            GetGenerationStatusUseCase,
        )
        return GetGenerationStatusUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            job_repo=SqlaJobRepository(session),
            targets=self._generation_targets(session),
        )

    def run_generation_use_case(self, session: Session) -> RunGenerationUseCase:
        from backend.application.use_cases.run_generation import RunGenerationUseCase
        return RunGenerationUseCase(
            source_repo=SqlaSourceRepository(session),
            candidate_repo=SqlaCandidateRepository(session),
            job_repo=SqlaJobRepository(session),
            candidate_sorter=self._candidate_sorter(session),
            targets=self._generation_targets(session),
        )

    def cancel_generation_use_case(self, session: Session) -> CancelGenerationUseCase:
        from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
        return CancelGenerationUseCase(job_repo=SqlaJobRepository(session))

    def get_queue_global_summary_use_case(
        self, session: Session,
    ) -> GetQueueGlobalSummaryUseCase:
        from backend.application.use_cases.get_queue_global_summary import (
            GetQueueGlobalSummaryUseCase,
        )
        return GetQueueGlobalSummaryUseCase(
            job_repo=SqlaJobRepository(session),
        )

    def get_queue_order_use_case(
        self, session: Session,
    ) -> GetQueueOrderUseCase:
        from backend.application.use_cases.get_queue_order import (
            GetQueueOrderUseCase,
        )
        return GetQueueOrderUseCase(
            job_repo=SqlaJobRepository(session),
            source_repo=SqlaSourceRepository(session),
        )

    def get_queue_failed_use_case(
        self, session: Session,
    ) -> GetQueueFailedUseCase:
        from backend.application.use_cases.get_queue_failed import (
            GetQueueFailedUseCase,
        )
        return GetQueueFailedUseCase(
            job_repo=SqlaJobRepository(session),
            source_repo=SqlaSourceRepository(session),
        )

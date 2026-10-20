from __future__ import annotations

import logging
import os
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from backend.application.source_intake.book_handler import BookHandler
from backend.application.source_intake.document_normalizer import DocumentNormalizer
from backend.application.source_intake.single_source_handler import SingleSourceHandler
from backend.application.source_intake.source_group_writer import SourceGroupWriter
from backend.application.source_intake.source_writer import SourceWriter
from backend.application.use_cases.add_manual_candidate import AddManualCandidateUseCase
from backend.application.use_cases.add_saved_phrase import AddSavedPhraseUseCase
from backend.application.use_cases.add_source import AddSourceUseCase
from backend.application.use_cases.analyze_text import AnalyzeTextUseCase
from backend.application.use_cases.build_bootstrap_index import BuildBootstrapIndexUseCase
from backend.application.use_cases.create_collection import CreateCollectionUseCase
from backend.application.use_cases.create_topic import CreateTopicUseCase
from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
from backend.application.use_cases.delete_collection import DeleteCollectionUseCase
from backend.application.use_cases.delete_source import DeleteSourceUseCase
from backend.application.use_cases.delete_sources import DeleteSourcesUseCase
from backend.application.use_cases.describe_input import DescribeInputUseCase
from backend.application.use_cases.fix_sections import FixSectionsUseCase
from backend.application.use_cases.generate_meaning import GenerateMeaningUseCase
from backend.application.use_cases.get_anki_status import GetAnkiStatusUseCase
from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
from backend.application.use_cases.get_candidates import GetCandidatesUseCase
from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
from backend.application.use_cases.get_learning_words import GetLearningWordsUseCase
from backend.application.use_cases.get_review import GetReviewUseCase
from backend.application.use_cases.get_review_documents import GetReviewDocumentsUseCase
from backend.application.use_cases.get_sources import GetSourcesUseCase
from backend.application.use_cases.get_stats import GetStatsUseCase
from backend.application.use_cases.list_collections import ListCollectionsUseCase
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.application.use_cases.manage_unknown_words import ManageUnknownWordsUseCase
from backend.application.use_cases.move_collection import MoveCollectionUseCase
from backend.application.use_cases.place_sources import PlaceSourcesUseCase
from backend.application.use_cases.preview_cloze import PreviewClozeUseCase
from backend.application.use_cases.process_source import ProcessSourceUseCase
from backend.application.use_cases.process_sources import ProcessSourcesUseCase
from backend.application.use_cases.rebuild_source import RebuildSourceUseCase
from backend.application.use_cases.refresh_topic import RefreshTopicUseCase
from backend.application.use_cases.rename_collection import RenameCollectionUseCase
from backend.application.use_cases.rename_source import RenameSourceUseCase
from backend.application.use_cases.render_names import RenderNamesUseCase
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.application.use_cases.report_candidate import ReportCandidateUseCase
from backend.application.use_cases.restore_collection import RestoreCollectionUseCase
from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.application.use_cases.save_cloze import SaveClozeUseCase
from backend.application.use_cases.scope_operation import ScopeOperationUseCase
from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase
from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
from backend.application.utils.candidate_factory import CandidateFactory
from backend.application.utils.candidate_sorter import CandidateSorter
from backend.application.utils.card_state_projector import CardStateProjector
from backend.application.utils.card_views import CardViews
from backend.application.utils.collected_phrases import CollectedPhrases
from backend.application.utils.decided_elsewhere import DecidedElsewhere
from backend.application.utils.decision_effects import DecisionEffects
from backend.application.utils.export_queue import ExportQueue
from backend.application.utils.frequent_word_threshold_resolver import (
    FrequentWordThresholdResolver,
)
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.application.utils.live_card_states import LiveCardStates
from backend.application.utils.phrase_reader import PhraseReader
from backend.application.utils.review_cards import ReviewCards
from backend.application.utils.review_progress import ReviewProgress
from backend.application.utils.rewrite_phrase import RewritePhrase
from backend.application.utils.section_stamper import SectionStamper
from backend.application.utils.source_ordering import SourceOrdering
from backend.application.utils.source_rebuilder import SourceRebuilder
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.application.utils.topic_generation import TopicGenerationProbe
from backend.application.utils.topic_phrase_collector import TopicPhraseCollector
from backend.application.utils.user_knowledge_reader import UserKnowledgeReader
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.ports.cefr_source import (
    CEFRSource,  # noqa: TC001 — used at runtime in list[CEFRSource]
)
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.services.input_kind_classifier import InputKindClassifier
from backend.domain.services.phrasal_verb_detector import PhrasalVerbDetector
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.fragment_selection_config import (
    FragmentSelectionConfig,
)
from backend.infrastructure.adapters.ai_model_mapping import model_id_for
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector
from backend.infrastructure.adapters.bing_image_source import BingImageSource
from backend.infrastructure.adapters.caching_document_analyzer import CachingDocumentAnalyzer
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
from backend.infrastructure.adapters.local_media_files import LocalMediaFiles
from backend.infrastructure.adapters.pillow_card_picture_encoder import PillowCardPictureEncoder
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer
from backend.infrastructure.adapters.spacy_document_analyzer import SpacyDocumentAnalyzer
from backend.infrastructure.adapters.spacy_text_analyzer import SpaCyTextAnalyzer
from backend.infrastructure.adapters.system_clock import SystemClock
from backend.infrastructure.adapters.throttled_http_file_downloader import (
    ThrottledHttpFileDownloader,
)
from backend.infrastructure.adapters.video_path_resolver import VideoPathResolverImpl
from backend.infrastructure.adapters.wiktionary_image_source import WiktionaryImageSource
from backend.infrastructure.adapters.wordfreq_frequency_provider import (
    WordfreqFrequencyProvider,
)
from backend.infrastructure.adapters.yandex_image_source import YandexImageSource
from backend.infrastructure.api.background_rebuild_launcher import (
    BackgroundSourcesRebuildLauncher,
)
from backend.infrastructure.config.prompts_loader import PromptsLoader
from backend.infrastructure.persistence.database import app_session_factory
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.session_work import SessionWork
from backend.infrastructure.persistence.sqla_anki_sync_repository import (
    SqlaAnkiSyncRepository,
)
from backend.infrastructure.persistence.sqla_bootstrap_index_repository import (
    SqlaBootstrapIndexRepository,
)
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_image_repository import (
    SqlaCandidateMeaningImageRepository,
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
from backend.infrastructure.persistence.sqla_card_query import SqlaCardQuery
from backend.infrastructure.persistence.sqla_card_report_repository import (
    SqlaCardReportRepository,
)
from backend.infrastructure.persistence.sqla_card_state_store import SqlaCardStateStore
from backend.infrastructure.persistence.sqla_collection_repository import (
    SqlaCollectionRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_queue import SqlaJobQueue
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_parse_cache import SqlaParseCache
from backend.infrastructure.persistence.sqla_settings_repository import (
    SqlaSettingsRepository,
)
from backend.infrastructure.persistence.sqla_source_operation_lock import (
    SqlaSourceOperationLock,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)
from backend.infrastructure.persistence.sqla_topic_target_repository import (
    SqlaTopicTargetRepository,
)
from backend.infrastructure.persistence.sqla_unit_of_work import SqlaUnitOfWork
from backend.infrastructure.persistence.sqla_word_decision_repository import (
    SqlaWordDecisionRepository,
)
from backend.infrastructure.persistence.sqla_word_mark_repository import (
    SqlaWordMarkRepository,
)
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from backend.infrastructure.readers.caching_reader import CachingFormatReader
from backend.infrastructure.readers.epub_format_reader import EpubFormatReader
from backend.infrastructure.readers.html_reader import HtmlReader
from backend.infrastructure.readers.markdown_reader import MarkdownReader
from backend.infrastructure.readers.plain_reader import PlainReader
from backend.infrastructure.readers.srt_reader import SrtReader
from backend.infrastructure.readers.video_file_reader import VideoFileReader
from backend.infrastructure.readers.youtube_reader import YouTubeReader
from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
    from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
    from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
    from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
    from backend.application.use_cases.download_pronunciation import DownloadPronunciationUseCase
    from backend.application.use_cases.download_video import DownloadVideoUseCase
    from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
    from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
    from backend.application.use_cases.enqueue_phrase_tts import EnqueuePhraseTTSUseCase
    from backend.application.use_cases.enqueue_topic_generation import (
        EnqueueTopicGenerationUseCase,
    )
    from backend.application.use_cases.generate_topic_targets import GenerateTopicTargetsUseCase
    from backend.application.use_cases.generate_tts import GenerateTTSUseCase
    from backend.application.use_cases.get_ai_usage_stats import GetAIUsageStatsUseCase
    from backend.application.use_cases.get_anki_templates import GetAnkiTemplatesUseCase
    from backend.application.use_cases.get_generation_status import GetGenerationStatusUseCase
    from backend.application.use_cases.get_media_storage_stats import GetMediaStorageStatsUseCase
    from backend.application.use_cases.get_queue_snapshot import GetQueueSnapshotUseCase
    from backend.application.use_cases.manage_anki_note_types import ManageAnkiNoteTypesUseCase
    from backend.application.use_cases.manage_queue import ManageQueueUseCase
    from backend.application.use_cases.paste_target_image import PasteTargetImageUseCase
    from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
    from backend.application.use_cases.regenerate_phrase_media import (
        RegeneratePhraseMediaUseCase,
    )
    from backend.application.use_cases.request_video_download import (
        RequestVideoDownloadUseCase,
    )
    from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
    from backend.application.use_cases.run_generation import RunGenerationUseCase
    from backend.application.use_cases.run_media_extraction_job import MediaExtractionUseCase
    from backend.application.use_cases.search_target_images import SearchTargetImagesUseCase
    from backend.application.utils.generation_targets import GenerationCards, GenerationTarget
    from backend.application.utils.job_phrases import JobPhrases
    from backend.application.utils.meaning_image_placer import MeaningImagePlacer
    from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
    from backend.application.utils.requested_cards import RequestedCards
    from backend.domain.ports.clock import Clock
    from backend.domain.ports.format_reader import FormatReader
    from backend.domain.ports.target_image_source import TargetImageSource
    from backend.domain.ports.url_source_fetcher import UrlSourceFetcher
    from backend.domain.value_objects.prompts_config import PromptsConfig
    from backend.infrastructure.adapters.kokoro_tts_generator import KokoroTTSGenerator

logger = logging.getLogger(__name__)

# Where a session keeps its knowledge scope (`Session.info`).
KNOWLEDGE_SCOPE_KEY = "knowledge_scope"
CHANGE_RECORDER_KEY = "change_recorder"


class Container:
    """Dependency injection container. Single point of assembly for all dependencies."""

    def __init__(
        self, session_factory: sessionmaker[Session] | None = None, clock: Clock | None = None,
    ) -> None:
        """`clock`: where every request and job reads `now`; the system's unless given."""

        from backend.infrastructure.adapters.ffmpeg_media_extractor import FfmpegMediaExtractor
        from backend.infrastructure.adapters.ffmpeg_subtitle_extractor import (
            FfmpegSubtitleExtractor,
        )

        self._text_analyzer = SpaCyTextAnalyzer()
        self._document_analyzer = SpacyDocumentAnalyzer(self._text_analyzer)
        self._text_cleaner = RegexTextCleaner()
        self._text_normalizer = SlangNormalizer()
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
        self._phrase_reader = PhraseReader(
            self._text_analyzer, self._cefr_classifier, self._frequency_provider,
        )
        self._anki_connector = AnkiConnectConnector()
        self._file_downloader = ThrottledHttpFileDownloader()
        # Dictionary first: when it has a picture, that picture shows exactly the word.
        self._target_image_sources: list[TargetImageSource] = [
            WiktionaryImageSource(),
            BingImageSource(),
            YandexImageSource(),
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
        youtube_fetcher = self._url_fetchers[0]
        self._format_detector = RegexFormatDetector(youtube_fetcher)
        self._format_readers: tuple[FormatReader, ...] = tuple(
            CachingFormatReader(reader)
            for reader in (
                PlainReader(self._file_reader),
                MarkdownReader(self._file_reader),
                HtmlReader(self._file_reader),
                EpubFormatReader(),
                SrtReader(self._file_reader),
                VideoFileReader(
                    self._file_reader, self._subtitle_extractor, self._subtitle_extractor,
                ),
                YouTubeReader(youtube_fetcher),
            )
        )
        self._document_normalizer = DocumentNormalizer(self._text_cleaner, self._text_normalizer)

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
        self._clock: Clock = clock or SystemClock()
        self._session_factory: sessionmaker[Session] | None = session_factory

    def _get_session_factory(self) -> sessionmaker[Session]:
        """The app's one session factory unless the container was given another; taken on
        first use, so a container made before the database is configured still finds it."""
        if self._session_factory is None:
            self._session_factory = app_session_factory()
        return self._session_factory

    def session_work(self) -> SessionWork:
        """Work outside a request, on sessions of its own."""
        return SessionWork(self._get_session_factory(), self._unit_of_work)

    def job_queue(self) -> SqlaJobQueue:
        return SqlaJobQueue(self.session_work())

    def job_repository(self, session: Session) -> SqlaJobRepository:
        return SqlaJobRepository(session)

    def add_manual_candidate_use_case(self, session: Session) -> AddManualCandidateUseCase:
        return AddManualCandidateUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
            phrase_reader=self._phrase_reader,
            stamper=self._section_stamper(session),
            lock=SqlaSourceOperationLock(session),
            card_views=self._card_views(session),
            decide_phrase=self.decide_phrase_use_case(session),
            unit_of_work=self._unit_of_work(session),
        )

    def set_phrase_boundary_use_case(self, session: Session) -> SetPhraseBoundaryUseCase:
        return SetPhraseBoundaryUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            phrase_reader=self._phrase_reader,
            lock=SqlaSourceOperationLock(session),
            stamper=self._section_stamper(session),
            unit_of_work=self._unit_of_work(session),
        )

    def get_review_documents_use_case(self, session: Session) -> GetReviewDocumentsUseCase:
        return GetReviewDocumentsUseCase(
            scope_resolver=self._scope_resolver(session),
            document_repo=SqlaDocumentRepository(session),
            card_query=SqlaCardQuery(session),
        )

    def add_saved_phrase_use_case(self, session: Session) -> AddSavedPhraseUseCase:
        return AddSavedPhraseUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            collected_phrases=self._collected_phrases(session),
            candidate_factory=self._candidate_factory(),
            phrase_reader=self._phrase_reader,
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            card_views=self._card_views(session),
            decide_phrase=self.decide_phrase_use_case(session),
            unit_of_work=self._unit_of_work(session),
        )

    def analyze_text_use_case(self) -> AnalyzeTextUseCase:
        return AnalyzeTextUseCase(
            document_analyzer=CachingDocumentAnalyzer(
                self._document_analyzer,
                SqlaParseCache(self._get_session_factory()),
                self._document_analyzer.version,
            ),
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
            fragment_selection_config=self._fragment_selection_config,
            usage_lookup=self._usage_source,
        )

    def add_source_use_case(self, session: Session) -> AddSourceUseCase:
        writer = SourceWriter(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            video_path_resolver=self._video_path_resolver,
        )
        return AddSourceUseCase(
            detector=self._format_detector,
            readers=self._format_readers,
            handlers=(
                SingleSourceHandler(Kind.TEXT),
                SingleSourceHandler(Kind.SONG),
                SingleSourceHandler(Kind.SUBTITLES),
                BookHandler(),
            ),
            normalizer=self._document_normalizer,
            file_reader=self._file_reader,
            group_writer=SourceGroupWriter(writer, SqlaCollectionRepository(session)),
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            unit_of_work=self._unit_of_work(session),
        )

    def render_names_use_case(self) -> RenderNamesUseCase:
        return RenderNamesUseCase()

    def describe_input_use_case(self) -> DescribeInputUseCase:
        return DescribeInputUseCase(
            detector=self._format_detector,
            file_reader=self._file_reader,
            text_analyzer=self._text_analyzer,
            classifier=InputKindClassifier(),
        )

    def create_topic_use_case(self, session: Session) -> CreateTopicUseCase:
        return CreateTopicUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            unit_of_work=self._unit_of_work(session),
        )

    def rename_source_use_case(self, session: Session) -> RenameSourceUseCase:
        return RenameSourceUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            unit_of_work=self._unit_of_work(session),
        )

    def delete_source_use_case(self, session: Session) -> DeleteSourceUseCase:
        return DeleteSourceUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            anki_sync=SqlaAnkiSyncRepository(session, self._change_recorder(session)),
            lock=SqlaSourceOperationLock(session),
            media_root=self._media_root,
            unit_of_work=self._unit_of_work(session),
        )

    def delete_sources_use_case(self, session: Session) -> DeleteSourcesUseCase:
        return DeleteSourcesUseCase(delete_source=self.delete_source_use_case(session))

    def get_sources_use_case(self, session: Session) -> GetSourcesUseCase:
        return GetSourcesUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            scope_resolver=self._scope_resolver(session),
            generation_probe=self._generation_probe(session),
            review_progress=self._review_progress(session),
            card_query=SqlaCardQuery(session),
            lock=SqlaSourceOperationLock(session),
        )

    def get_review_use_case(self, session: Session) -> GetReviewUseCase:
        return GetReviewUseCase(
            card_views=self._card_views(session),
            scope_resolver=self._scope_resolver(session),
            card_query=SqlaCardQuery(session),
            lock=SqlaSourceOperationLock(session),
        )

    def create_collection_use_case(self, session: Session) -> CreateCollectionUseCase:
        return CreateCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

    def list_collections_use_case(self, session: Session) -> ListCollectionsUseCase:
        return ListCollectionsUseCase(
            collection_repo=SqlaCollectionRepository(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            review_progress=self._review_progress(session),
            generation_probe=self._generation_probe(session),
            lock=SqlaSourceOperationLock(session),
            card_query=SqlaCardQuery(session),
        )

    def rename_collection_use_case(self, session: Session) -> RenameCollectionUseCase:
        return RenameCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

    def delete_collection_use_case(self, session: Session) -> DeleteCollectionUseCase:
        return DeleteCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            unit_of_work=self._unit_of_work(session),
        )

    def move_collection_use_case(self, session: Session) -> MoveCollectionUseCase:
        return MoveCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

    def restore_collection_use_case(self, session: Session) -> RestoreCollectionUseCase:
        return RestoreCollectionUseCase(
            collection_repo=SqlaCollectionRepository(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            unit_of_work=self._unit_of_work(session),
        )

    def place_sources_use_case(self, session: Session) -> PlaceSourcesUseCase:
        return PlaceSourcesUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            collection_repo=SqlaCollectionRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

    def process_source_use_case(self, session: Session) -> ProcessSourceUseCase:
        return ProcessSourceUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            collected_phrases=self._collected_phrases(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
            rebuilder=self._source_rebuilder(session),
            topic_phrase_collector=self._topic_phrase_collector(session),
        )

    def fix_sections_use_case(self, session: Session) -> FixSectionsUseCase:
        return FixSectionsUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            stamper=self._section_stamper(session),
            rebuild_source=self.rebuild_source_use_case(session),
            unit_of_work=self._unit_of_work(session),
        )

    def rebuild_source_use_case(self, session: Session) -> RebuildSourceUseCase:
        return RebuildSourceUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
            rebuilder=self._source_rebuilder(session),
        )

    def refresh_topic_use_case(self, session: Session) -> RefreshTopicUseCase:
        return RefreshTopicUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            collected_phrases=self._collected_phrases(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
            collector=self._topic_phrase_collector(session),
        )

    def scope_operation_use_case(self, session: Session) -> ScopeOperationUseCase:
        return ScopeOperationUseCase(
            scope_resolver=self._scope_resolver(session),
            rebuild_source=self.rebuild_source_use_case(session),
            refresh_topic=self.refresh_topic_use_case(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _source_rebuilder(self, session: Session) -> SourceRebuilder:
        settings_repo = SqlaSettingsRepository(session, self._change_recorder(session))
        return SourceRebuilder(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            anki_sync=SqlaAnkiSyncRepository(session, self._change_recorder(session)),
            job_repo=SqlaJobRepository(session),
            media_repo=SqlaCandidateMediaRepository(session, self._change_recorder(session)),
            media_files=LocalMediaFiles(self._media_root),
            settings_repo=settings_repo,
            vocabulary=self._user_vocabulary(session),
            threshold_resolver=self._threshold_resolver(session),
            stamper=self._section_stamper(session),
            analyze_text_use_case=self.analyze_text_use_case(),
            unit_of_work=self._unit_of_work(session),
            weight_unknown=self._fragment_selection_config.scoring.weight_unknown,
        )

    def process_sources_use_case(self, session: Session) -> ProcessSourcesUseCase:
        return ProcessSourcesUseCase(
            scope_resolver=self._scope_resolver(session),
            generation_probe=self._generation_probe(session),
            process_source=self.process_source_use_case(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _candidate_factory(self) -> CandidateFactory:
        return CandidateFactory(
            text_analyzer=self._text_analyzer,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            phrasal_verb_detector=PhrasalVerbDetector(self._phrasal_verb_dictionary),
        )

    def _collected_phrases(self, session: Session) -> CollectedPhrases:
        return CollectedPhrases(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            stamper=self._section_stamper(session),
        )

    def _topic_phrase_collector(self, session: Session) -> TopicPhraseCollector:
        return TopicPhraseCollector(
            topic_target_repo=SqlaTopicTargetRepository(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            knowledge=self._user_knowledge(session),
            candidate_factory=self._candidate_factory(),
            phrase_reader=self._phrase_reader,
        )

    def enqueue_topic_generation_use_case(
        self, session: Session,
    ) -> EnqueueTopicGenerationUseCase:
        from backend.application.use_cases.enqueue_topic_generation import (
            EnqueueTopicGenerationUseCase,
        )
        return EnqueueTopicGenerationUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            topic_target_repo=SqlaTopicTargetRepository(session),
            job_repo=SqlaJobRepository(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
        )

    def generate_topic_targets_use_case(self, session: Session) -> GenerateTopicTargetsUseCase:
        from backend.application.use_cases.generate_topic_targets import (
            GenerateTopicTargetsUseCase,
        )
        settings_repo = SqlaSettingsRepository(session, self._change_recorder(session))
        return GenerateTopicTargetsUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            topic_target_repo=SqlaTopicTargetRepository(session),
            settings_repo=settings_repo,
            ai_service=self._ai_service(settings_repo),
            prompts_config=self._prompts_config,
            unit_of_work=self._unit_of_work(session),
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

    def get_candidates_use_case(self, session: Session) -> GetCandidatesUseCase:
        return GetCandidatesUseCase(
            card_views=self._card_views(session),
        )

    def report_candidate_use_case(self, session: Session) -> ReportCandidateUseCase:
        return ReportCandidateUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            report_repo=SqlaCardReportRepository(session),
            knowledge=self._user_knowledge(session),
            effects=self._decision_effects(session),
            unit_of_work=self._unit_of_work(session),
        )

    def decide_phrase_use_case(self, session: Session) -> DecidePhraseUseCase:
        return DecidePhraseUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            word_states=SqlaWordStateRepository(session, self._change_recorder(session)),
            vocabulary=self._user_vocabulary(session),
            effects=self._decision_effects(session),
            lock=SqlaSourceOperationLock(session),
            card_views=self._card_views(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _decision_effects(self, session: Session) -> DecisionEffects:
        return DecisionEffects(
            word_states=SqlaWordStateRepository(session, self._change_recorder(session)),
            vocabulary=self._user_vocabulary(session),
            decision_repo=SqlaWordDecisionRepository(session),
            anki_sync=SqlaAnkiSyncRepository(session, self._change_recorder(session)),
            lock=SqlaSourceOperationLock(session),
        )

    def save_cloze_use_case(self, session: Session) -> SaveClozeUseCase:
        return SaveClozeUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            cloze_repo=SqlaCandidateClozeRepository(session, self._change_recorder(session)),
            card_views=self._card_views(session),
            decide_phrase=self.decide_phrase_use_case(session),
            builder=ClozeBuilder(),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
        )

    def preview_cloze_use_case(self, session: Session) -> PreviewClozeUseCase:
        return PreviewClozeUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            builder=ClozeBuilder(),
        )

    def replace_with_example_use_case(self, session: Session) -> ReplaceWithExampleUseCase:
        return ReplaceWithExampleUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            phrase_reader=self._phrase_reader,
            stamper=self._section_stamper(session),
            job_repo=SqlaJobRepository(session),
            lock=SqlaSourceOperationLock(session),
            card_views=self._card_views(session),
            word_states=SqlaWordStateRepository(session, self._change_recorder(session)),
            vocabulary=self._user_vocabulary(session),
            effects=self._decision_effects(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _threshold_resolver(self, session: Session) -> FrequentWordThresholdResolver:
        return FrequentWordThresholdResolver(
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            decision_repo=SqlaWordDecisionRepository(session),
        )

    def _section_stamper(self, session: Session) -> SectionStamper:
        return SectionStamper(
            knowledge=self._user_knowledge(session),
            threshold_resolver=self._threshold_resolver(session),
        )

    def _candidate_sorter(self, session: Session) -> CandidateSorter:
        return CandidateSorter(
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            threshold_resolver=self._threshold_resolver(session),
            knowledge=self._user_knowledge(session),
        )

    def _generation_probe(self, session: Session) -> TopicGenerationProbe:
        return TopicGenerationProbe(
            job_repo=SqlaJobRepository(session),
            topic_target_repo=SqlaTopicTargetRepository(session),
        )

    def _scope_resolver(self, session: Session) -> SourceScopeResolver:
        return SourceScopeResolver(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            collection_repo=SqlaCollectionRepository(session),
            ordering=SourceOrdering(
                settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
                review_progress=self._review_progress(session),
                generation_probe=self._generation_probe(session),
                candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            ),
        )

    def _review_progress(self, session: Session) -> ReviewProgress:
        return ReviewProgress(
            card_query=SqlaCardQuery(session),
            candidate_sorter=self._candidate_sorter(session),
            decided_elsewhere=DecidedElsewhere(self._user_vocabulary(session)),
        )

    def _card_views(self, session: Session) -> CardViews:
        return CardViews(
            review_cards=ReviewCards(
                SqlaCandidateRepository(session, self._change_recorder(session)),
                SqlaOccurrenceRepository(session, self._change_recorder(session)),
                SqlaWordStateRepository(session, self._change_recorder(session)),
                self._user_vocabulary(session),
            ),
            candidate_sorter=self._candidate_sorter(session),
            job_repo=SqlaJobRepository(session),
            report_repo=SqlaCardReportRepository(session),
            scope_resolver=self._scope_resolver(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
        )

    def _review_cards(self, session: Session) -> ReviewCards:
        return ReviewCards(
            SqlaCandidateRepository(session, self._change_recorder(session)),
            SqlaOccurrenceRepository(session, self._change_recorder(session)),
            SqlaWordStateRepository(session, self._change_recorder(session)),
            self._user_vocabulary(session),
        )

    def card_state_projector(self, session: Session) -> CardStateProjector:
        return CardStateProjector(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            card_query=SqlaCardQuery(session),
            word_states=SqlaWordStateRepository(session, self._change_recorder(session)),
            knowledge=self._user_knowledge(session),
            vocabulary=self._user_vocabulary(session),
            store=SqlaCardStateStore(session),
        )

    def rebuild_card_states(self) -> None:
        """The whole projection computed anew in one write transaction of its own."""
        self.session_work().write(lambda session: self.card_state_projector(session).rebuild())

    def live_card_states(self, session: Session) -> LiveCardStates:
        return LiveCardStates(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            review_cards=self._review_cards(session),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            knowledge=self._user_knowledge(session),
            vocabulary=self._user_vocabulary(session),
        )

    def _user_vocabulary(self, session: Session) -> UserVocabulary:
        return UserVocabulary(
            word_mark_repo=SqlaWordMarkRepository(session, self._change_recorder(session)),
            scope=self.knowledge_scope(session),
        )

    def _unit_of_work(self, session: Session) -> SqlaUnitOfWork:
        return SqlaUnitOfWork(session, self.knowledge_scope(session))

    def _change_recorder(self, session: Session) -> SessionChangeRecorder:
        """One per database session, shared by every owner of facts built for it."""
        recorder = session.info.get(CHANGE_RECORDER_KEY)
        if not isinstance(recorder, SessionChangeRecorder):
            recorder = SessionChangeRecorder(session)
            session.info[CHANGE_RECORDER_KEY] = recorder
        return recorder

    def knowledge_scope(self, session: Session) -> KnowledgeScope:
        """One per database session, so one per request and one per job: a single `now`
        and one snapshot of what the user knows, shared by everything built for it."""
        scope = session.info.get(KNOWLEDGE_SCOPE_KEY)
        if not isinstance(scope, KnowledgeScope):
            scope = KnowledgeScope(
                clock=self._clock,
                word_mark_repo=SqlaWordMarkRepository(session, self._change_recorder(session)),
                learning_query=SqlaLearningQuery(session),
            )
            session.info[KNOWLEDGE_SCOPE_KEY] = scope
        return scope

    @property
    def phrase_reader(self) -> PhraseReader:
        return self._phrase_reader

    def _user_knowledge(self, session: Session) -> UserKnowledgeReader:
        return UserKnowledgeReader(
            vocabulary=self._user_vocabulary(session),
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            threshold_resolver=self._threshold_resolver(session),
        )

    def _rewrite_phrase(self, session: Session) -> RewritePhrase:
        return RewritePhrase(
            phrase_reader=self._phrase_reader,
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            stamper=self._section_stamper(session),
        )

    def manage_unknown_words_use_case(self, session: Session) -> ManageUnknownWordsUseCase:
        return ManageUnknownWordsUseCase(
            vocabulary=self._user_vocabulary(session),
            unit_of_work=self._unit_of_work(session),
        )

    def manage_known_words_use_case(self, session: Session) -> ManageKnownWordsUseCase:
        return ManageKnownWordsUseCase(
            vocabulary=self._user_vocabulary(session),
            effects=self._decision_effects(session),
            unit_of_work=self._unit_of_work(session),
        )

    def manage_settings_use_case(self, session: Session) -> ManageSettingsUseCase:
        return ManageSettingsUseCase(
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            threshold_resolver=self._threshold_resolver(session),
            unit_of_work=self._unit_of_work(session),
            rebuild_launcher=self._rebuild_launcher(),
        )

    def _rebuild_launcher(self) -> BackgroundSourcesRebuildLauncher:
        """Works in sessions of its own, from the container's session factory: an API
        override of `get_session_factory` does not reach it."""
        work = self.session_work()
        return BackgroundSourcesRebuildLauncher(
            scope_operations=lambda: work.open(self.scope_operation_use_case),
        )

    def get_anki_status_use_case(self, session: Session) -> GetAnkiStatusUseCase:
        return GetAnkiStatusUseCase(
            connector=self._anki_connector,
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            template_renderer=self._anki_template_renderer,
        )

    def sync_to_anki_use_case(self, session: Session) -> SyncToAnkiUseCase:
        return SyncToAnkiUseCase(
            export_queue=self._export_queue(session),
            anki_connector=self._anki_connector,
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            template_renderer=self._anki_template_renderer,
            cloze_builder=ClozeBuilder(),
            scope_resolver=self._scope_resolver(session),
            vocabulary=self._user_vocabulary(session),
            effects=self._decision_effects(session),
            word_states=SqlaWordStateRepository(session, self._change_recorder(session)),
            unit_of_work=self._unit_of_work(session),
        )

    def get_learning_words_use_case(self, session: Session) -> GetLearningWordsUseCase:
        return GetLearningWordsUseCase(vocabulary=self._user_vocabulary(session))

    def get_export_cards_use_case(self, session: Session) -> GetExportCardsUseCase:
        return GetExportCardsUseCase(
            export_queue=self._export_queue(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            cloze_builder=ClozeBuilder(),
            scope_resolver=self._scope_resolver(session),
        )

    def _export_queue(self, session: Session) -> ExportQueue:
        return ExportQueue(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            word_states=SqlaWordStateRepository(session, self._change_recorder(session)),
            vocabulary=self._user_vocabulary(session),
        )

    def generate_meaning_use_case(self, session: Session) -> GenerateMeaningUseCase:
        return GenerateMeaningUseCase(
            cards=self._requested_cards(session),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            meaning_repo=SqlaCandidateMeaningRepository(session, self._change_recorder(session)),
            ai_service=self._ai_service(SqlaSettingsRepository(
                session, self._change_recorder(session),
            )),
            prompts_config=self._prompts_config,
            unit_of_work=self._unit_of_work(session),
        )

    def meaning_generation_use_case(self, session: Session) -> MeaningGenerationUseCase:
        return MeaningGenerationUseCase(
            job_phrases=self._job_phrases(session),
            meaning_repo=SqlaCandidateMeaningRepository(session, self._change_recorder(session)),
            ai_service=self._ai_service(SqlaSettingsRepository(
                session, self._change_recorder(session),
            )),
            prompts_config=self._prompts_config,
            unit_of_work=self._unit_of_work(session),
        )

    def phrase_polish_use_case(self, session: Session) -> PhrasePolishUseCase:
        from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
        settings_repo = SqlaSettingsRepository(session, self._change_recorder(session))
        return PhrasePolishUseCase(
            job_phrases=self._job_phrases(session),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            settings_repo=settings_repo,
            enrichment_reset=self._phrase_enrichment_reset(session),
            ai_service=self._ai_service(settings_repo),
            prompts_config=self._prompts_config,
            rewrite_phrase=self._rewrite_phrase(session),
            stamper=self._section_stamper(session),
            unit_of_work=self._unit_of_work(session),
        )

    def enqueue_phrase_polish_use_case(self, session: Session) -> EnqueuePhrasePolishUseCase:
        from backend.application.use_cases.enqueue_phrase_polish import (
            EnqueuePhrasePolishUseCase,
        )
        return EnqueuePhrasePolishUseCase(
            cards=self._requested_cards(session),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            job_repo=SqlaJobRepository(session),
            stamper=self._section_stamper(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _job_phrases(self, session: Session) -> JobPhrases:
        from backend.application.utils.job_phrases import JobPhrases
        return JobPhrases(
            SqlaCandidateRepository(session, self._change_recorder(session)),
            SqlaOccurrenceRepository(session, self._change_recorder(session)),
            SqlaWordStateRepository(session, self._change_recorder(session)),
            self._user_vocabulary(session),
        )

    def _requested_cards(self, session: Session) -> RequestedCards:
        from backend.application.utils.requested_cards import RequestedCards
        return RequestedCards(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            lock=SqlaSourceOperationLock(session),
        )

    def _generation_cards(self, session: Session) -> GenerationCards:
        from backend.application.utils.generation_targets import GenerationCards
        return GenerationCards(
            SqlaCandidateRepository(session, self._change_recorder(session)),
            SqlaOccurrenceRepository(session, self._change_recorder(session)),
            SqlaWordStateRepository(session, self._change_recorder(session)),
            self._user_vocabulary(session),
        )

    def revert_phrase_polish_use_case(self, session: Session) -> RevertPhrasePolishUseCase:
        from backend.application.use_cases.revert_phrase_polish import (
            RevertPhrasePolishUseCase,
        )
        return RevertPhrasePolishUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            enrichment_reset=self._phrase_enrichment_reset(session),
            lock=SqlaSourceOperationLock(session),
            stamper=self._section_stamper(session),
            unit_of_work=self._unit_of_work(session),
        )

    def edit_card_phrase_use_case(self, session: Session) -> EditCardPhraseUseCase:
        from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
        return EditCardPhraseUseCase(
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            rewrite_phrase=self._rewrite_phrase(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _phrase_enrichment_reset(self, session: Session) -> PhraseEnrichmentReset:
        from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
        return PhraseEnrichmentReset(
            meaning_repo=SqlaCandidateMeaningRepository(session, self._change_recorder(session)),
            tts_repo=SqlaCandidateTTSRepository(session, self._change_recorder(session)),
        )

    def get_stats_use_case(self, session: Session) -> GetStatsUseCase:
        return GetStatsUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            vocabulary=self._user_vocabulary(session),
            export_queue=self._export_queue(session),
            job_repo=SqlaJobRepository(session),
        )

    def build_bootstrap_index_use_case(self, session: Session) -> BuildBootstrapIndexUseCase:
        return BuildBootstrapIndexUseCase(
            corpus_provider=self._word_corpus_provider,
            cefr_classifier=self._cefr_classifier,
            frequency_provider=self._frequency_provider,
            index_repo=SqlaBootstrapIndexRepository(session),
            phrasal_verb_dictionary=self._phrasal_verb_dictionary,
            unit_of_work=self._unit_of_work(session),
        )

    def get_bootstrap_words_use_case(self, session: Session) -> GetBootstrapWordsUseCase:
        return GetBootstrapWordsUseCase(
            index_repo=SqlaBootstrapIndexRepository(session),
            vocabulary=self._user_vocabulary(session),
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
        )

    def media_root(self) -> str:
        return self._media_root

    @property
    def tts_generator(self) -> KokoroTTSGenerator:
        if self._tts_generator is None:
            from backend.infrastructure.adapters.kokoro_tts_generator import KokoroTTSGenerator
            self._tts_generator = KokoroTTSGenerator()
        return self._tts_generator

    def prompts_config(self) -> PromptsConfig:
        return self._prompts_config

    def lazy_media_reconciler(self) -> LazyMediaReconciler:
        if self._lazy_media_reconciler is None:
            self._lazy_media_reconciler = LazyMediaReconciler(
                work=self.session_work(),
                media_root=self._media_root,
            )
        return self._lazy_media_reconciler

    def media_extraction_use_case(self, session: Session) -> MediaExtractionUseCase:
        from backend.application.use_cases.run_media_extraction_job import (
            MediaExtractionUseCase,
        )
        return MediaExtractionUseCase(
            job_phrases=self._job_phrases(session),
            media_repo=SqlaCandidateMediaRepository(session, self._change_recorder(session)),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            media_extractor=self._media_extractor,
            media_files=LocalMediaFiles(self._media_root),
            video_path_resolver=self._video_path_resolver,
            unit_of_work=self._unit_of_work(session),
        )

    def get_media_storage_stats_use_case(self, session: Session) -> GetMediaStorageStatsUseCase:
        from backend.application.use_cases.get_media_storage_stats import (
            GetMediaStorageStatsUseCase,
        )
        return GetMediaStorageStatsUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            media_root=self._media_root,
        )

    def cleanup_media_use_case(self, session: Session) -> CleanupMediaUseCase:
        from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
        return CleanupMediaUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            media_repo=SqlaCandidateMediaRepository(session, self._change_recorder(session)),
            image_repo=SqlaCandidateMeaningImageRepository(
                session, self._change_recorder(session),
            ),
            media_root=self._media_root,
            unit_of_work=self._unit_of_work(session),
        )

    def regenerate_phrase_media_use_case(
        self, session: Session
    ) -> RegeneratePhraseMediaUseCase:
        from backend.application.use_cases.regenerate_phrase_media import (
            RegeneratePhraseMediaUseCase,
        )
        return RegeneratePhraseMediaUseCase(
            cards=self._requested_cards(session),
            occurrence_repo=SqlaOccurrenceRepository(session, self._change_recorder(session)),
            media_repo=SqlaCandidateMediaRepository(session, self._change_recorder(session)),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            document_repo=SqlaDocumentRepository(session),
            media_extractor=self._media_extractor,
            media_files=LocalMediaFiles(self._media_root),
            video_path_resolver=self._video_path_resolver,
            unit_of_work=self._unit_of_work(session),
        )

    def download_video_use_case(self, session: Session) -> DownloadVideoUseCase:
        from backend.application.use_cases.download_video import DownloadVideoUseCase
        return DownloadVideoUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            video_downloader=self._video_downloader,
            video_path_resolver=self._video_path_resolver,
            unit_of_work=self._unit_of_work(session),
        )

    def cleanup_youtube_video_use_case(self, session: Session) -> CleanupYoutubeVideoUseCase:
        from backend.application.use_cases.cleanup_youtube_video import CleanupYoutubeVideoUseCase
        return CleanupYoutubeVideoUseCase(
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            media_repo=SqlaCandidateMediaRepository(session, self._change_recorder(session)),
            job_repo=SqlaJobRepository(session),
            video_path_resolver=self._video_path_resolver,
            unit_of_work=self._unit_of_work(session),
        )

    def candidate_meaning_repository(self, session: Session) -> SqlaCandidateMeaningRepository:
        return SqlaCandidateMeaningRepository(session, self._change_recorder(session))

    def candidate_media_repository(self, session: Session) -> SqlaCandidateMediaRepository:
        return SqlaCandidateMediaRepository(session, self._change_recorder(session))

    def manage_anki_note_types_use_case(self, session: Session) -> ManageAnkiNoteTypesUseCase:
        from backend.application.use_cases.manage_anki_note_types import (
            ManageAnkiNoteTypesUseCase,
        )
        return ManageAnkiNoteTypesUseCase(
            connector=self._anki_connector,
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            template_renderer=self._anki_template_renderer,
        )

    def get_anki_templates_use_case(self, session: Session) -> GetAnkiTemplatesUseCase:
        from backend.application.use_cases.get_anki_templates import GetAnkiTemplatesUseCase
        return GetAnkiTemplatesUseCase(
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            template_renderer=self._anki_template_renderer,
        )

    def candidate_pronunciation_repository(
        self, session: Session,
    ) -> SqlaCandidatePronunciationRepository:
        return SqlaCandidatePronunciationRepository(session, self._change_recorder(session))

    def download_pronunciation_use_case(
        self, session: Session,
    ) -> DownloadPronunciationUseCase:
        from backend.application.use_cases.download_pronunciation import (
            DownloadPronunciationUseCase,
        )
        return DownloadPronunciationUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            pronunciation_repo=SqlaCandidatePronunciationRepository(
                session, self._change_recorder(session),
            ),
            pronunciation_source=self._pronunciation_source,
            file_downloader=self._file_downloader,
            media_root=self._media_root,
            unit_of_work=self._unit_of_work(session),
        )

    def search_target_images_use_case(self, session: Session) -> SearchTargetImagesUseCase:
        from backend.application.use_cases.search_target_images import (
            SearchTargetImagesUseCase,
        )
        return SearchTargetImagesUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            image_sources=self._target_image_sources,
        )

    def apply_target_image_use_case(self, session: Session) -> ApplyTargetImageUseCase:
        from backend.application.use_cases.apply_target_image import ApplyTargetImageUseCase
        return ApplyTargetImageUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            image_sources=self._target_image_sources,
            file_downloader=self._image_downloader,
            picture_placer=self._meaning_image_placer(session),
            unit_of_work=self._unit_of_work(session),
        )

    def paste_target_image_use_case(self, session: Session) -> PasteTargetImageUseCase:
        from backend.application.use_cases.paste_target_image import PasteTargetImageUseCase
        return PasteTargetImageUseCase(
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
            picture_placer=self._meaning_image_placer(session),
            unit_of_work=self._unit_of_work(session),
        )

    def _meaning_image_placer(self, session: Session) -> MeaningImagePlacer:
        from backend.application.utils.meaning_image_placer import MeaningImagePlacer
        return MeaningImagePlacer(
            image_repo=SqlaCandidateMeaningImageRepository(
                session, self._change_recorder(session),
            ),
            picture_encoder=self._picture_encoder,
            media_root=self._media_root,
        )

    def generate_tts_use_case(self, session: Session) -> GenerateTTSUseCase:
        from backend.application.use_cases.generate_tts import GenerateTTSUseCase
        return GenerateTTSUseCase(
            job_phrases=self._job_phrases(session),
            tts_repo=SqlaCandidateTTSRepository(session, self._change_recorder(session)),
            tts_generator=self.tts_generator,
            settings_repo=SqlaSettingsRepository(session, self._change_recorder(session)),
            media_files=LocalMediaFiles(self._media_root),
            unit_of_work=self._unit_of_work(session),
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
            PolishTarget(
                SqlaOccurrenceRepository(session, self._change_recorder(session)),
                self._section_stamper(session),
            ),
            MeaningTarget(SqlaCandidateMeaningRepository(session, self._change_recorder(session))),
            MediaTarget(),
            PronunciationTarget(),
            TTSTarget(),
        ]

    def get_generation_status_use_case(self, session: Session) -> GetGenerationStatusUseCase:
        from backend.application.use_cases.get_generation_status import (
            GetGenerationStatusUseCase,
        )
        return GetGenerationStatusUseCase(
            scope_resolver=self._scope_resolver(session),
            cards=self._generation_cards(session),
            job_repo=SqlaJobRepository(session),
            candidate_sorter=self._candidate_sorter(session),
            targets=self._generation_targets(session),
        )

    def run_generation_use_case(self, session: Session) -> RunGenerationUseCase:
        from backend.application.use_cases.run_generation import RunGenerationUseCase
        return RunGenerationUseCase(
            scope_resolver=self._scope_resolver(session),
            cards=self._generation_cards(session),
            job_repo=SqlaJobRepository(session),
            candidate_sorter=self._candidate_sorter(session),
            targets=self._generation_targets(session),
            lock=SqlaSourceOperationLock(session),
            unit_of_work=self._unit_of_work(session),
        )

    def cancel_generation_use_case(self, session: Session) -> CancelGenerationUseCase:
        from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
        return CancelGenerationUseCase(
            job_repo=SqlaJobRepository(session), scope_resolver=self._scope_resolver(session),
            unit_of_work=self._unit_of_work(session),
        )

    def get_queue_snapshot_use_case(self, session: Session) -> GetQueueSnapshotUseCase:
        from backend.application.use_cases.get_queue_snapshot import GetQueueSnapshotUseCase
        return GetQueueSnapshotUseCase(
            job_repo=SqlaJobRepository(session),
            source_repo=SqlaSourceRepository(session, self._change_recorder(session)),
            candidate_repo=SqlaCandidateRepository(session, self._change_recorder(session)),
        )

    def manage_queue_use_case(self, session: Session) -> ManageQueueUseCase:
        from backend.application.use_cases.manage_queue import ManageQueueUseCase
        return ManageQueueUseCase(
            job_repo=SqlaJobRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

    def request_video_download_use_case(
        self, session: Session,
    ) -> RequestVideoDownloadUseCase:
        from backend.application.use_cases.request_video_download import (
            RequestVideoDownloadUseCase,
        )
        return RequestVideoDownloadUseCase(
            scope_resolver=self._scope_resolver(session),
            job_repo=SqlaJobRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

    def enqueue_phrase_tts_use_case(self, session: Session) -> EnqueuePhraseTTSUseCase:
        from backend.application.use_cases.enqueue_phrase_tts import EnqueuePhraseTTSUseCase
        return EnqueuePhraseTTSUseCase(
            cards=self._requested_cards(session), job_repo=SqlaJobRepository(session),
            unit_of_work=self._unit_of_work(session),
        )

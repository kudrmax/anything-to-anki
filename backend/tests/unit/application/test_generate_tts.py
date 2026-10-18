from __future__ import annotations

from dataclasses import replace
from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.generate_tts import ALL_VOICES, GenerateTTSUseCase
from backend.application.utils.generation_targets import GenerationCard
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.adapters.local_media_files import LocalMediaFiles

from tests.card_support import context
from tests.phrase_support import make_occurrence
from tests.word_support import phrase_id_of


@pytest.fixture()
def deps(tmp_path: Path) -> dict:
    job_phrases = MagicMock()
    job_phrases.holds.return_value = True
    tts_repo = MagicMock()
    tts_generator = MagicMock()
    tts_generator.generate_audio.side_effect = (
        lambda _text, path, _voice, _speed: path.write_bytes(b"speech")
    )
    settings_repo = MagicMock()
    return {
        "job_phrases": job_phrases,
        "tts_repo": tts_repo,
        "tts_generator": tts_generator,
        "settings_repo": settings_repo,
        "media_files": LocalMediaFiles(str(tmp_path)),
    }


def _make_candidate(
    candidate_id: int = 1,
    source_id: int = 10,
    context_fragment: str = "She couldn't help but procrastinate.",
) -> GenerationCard:
    """A card of the word and its phrase `phrase_id_of(candidate_id)`."""
    word = StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma="procrastinate",
        pos="VERB",
        status=WordStatus.LEARN,
        cefr_level=None,
        zipf_frequency=4.0,
        occurrences=1,
    )
    shown = replace(
        make_occurrence(context_fragment, candidate_id=candidate_id),
        id=phrase_id_of(candidate_id),
    )
    return GenerationCard.of(word, shown, context(word, shown))


@pytest.mark.unit
def test_generate_tts_calls_generator(deps: dict, tmp_path: Path) -> None:
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(1), 0))

    deps["tts_generator"].generate_audio.assert_called_once()
    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][0] == "She couldn't help but procrastinate."
    assert str(call_args[0][1]).endswith(".m4a")
    assert (tmp_path / "10" / f"p{phrase_id_of(1)}_tts.m4a").read_bytes() == b"speech"
    assert call_args[0][2] in ALL_VOICES
    assert call_args[0][3] == 1.0

    deps["tts_repo"].upsert_for_phrase.assert_called_once()


@pytest.mark.unit
def test_generate_tts_respects_voice_setting(deps: dict) -> None:
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        '["bf_emma"]' if key == "tts_enabled_voices" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(1), 0))

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][2] == "bf_emma"


@pytest.mark.unit
def test_generate_tts_respects_speed_setting(deps: dict) -> None:
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        "0.8" if key == "tts_speed" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(1), 0))

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][3] == 0.8


@pytest.mark.unit
def test_generate_tts_skips_a_phrase_gone_or_changed(deps: dict) -> None:
    deps["job_phrases"].card.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(999, 0))

    deps["tts_generator"].generate_audio.assert_not_called()
    deps["tts_repo"].upsert_for_phrase.assert_not_called()


@pytest.mark.unit
def test_execute_one_overwrites_existing_tts(deps: dict) -> None:
    """Upsert is called even if TTS already exists — overwrites with new path."""
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(1), 0))

    # upsert is called — whether record existed or not, it's the repo's job
    deps["tts_repo"].upsert_for_phrase.assert_called_once()
    phrase_id, tts_entity = deps["tts_repo"].upsert_for_phrase.call_args[0]
    assert (phrase_id, tts_entity.candidate_id) == (phrase_id_of(1), 1)
    assert tts_entity.audio_path.endswith(f"p{phrase_id_of(1)}_tts.m4a")


@pytest.mark.unit
def test_pick_voice_with_empty_enabled_list_falls_back(deps: dict) -> None:
    """When enabled voices list is empty JSON array, fall back to ALL_VOICES."""
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        "[]" if key == "tts_enabled_voices" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(1), 0))

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][2] in ALL_VOICES


@pytest.mark.unit
def test_pick_voice_result_always_from_enabled_list(deps: dict) -> None:
    """When multiple voices enabled, picked voice is always from that list."""
    enabled = ["bf_emma", "am_adam", "af_heart"]
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        '["bf_emma", "am_adam", "af_heart"]' if key == "tts_enabled_voices" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    # Run multiple times to verify randomness stays within bounds
    for _ in range(20):
        use_case.execute_one(PhraseRef(phrase_id_of(1), 0))
        call_args = deps["tts_generator"].generate_audio.call_args
        assert call_args[0][2] in enabled


@pytest.mark.unit
def test_get_speed_with_invalid_string_falls_back_to_default(deps: dict) -> None:
    """Invalid speed string (e.g. 'abc') falls back to default 1.0."""
    candidate = _make_candidate()
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        "abc" if key == "tts_speed" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(1), 0))

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][3] == 1.0


@pytest.mark.unit
def test_output_directory_created_under_media_root(deps: dict, tmp_path: Path) -> None:
    """Output directory is created based on source_id under media_root."""
    candidate = _make_candidate(candidate_id=5, source_id=42)
    deps["job_phrases"].card.return_value = candidate
    deps["settings_repo"].get.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(PhraseRef(phrase_id_of(5), 0))

    call_args = deps["tts_generator"].generate_audio.call_args
    out_path = Path(str(call_args[0][1]))
    assert out_path.parent == tmp_path / "42"
    assert [p.name for p in (tmp_path / "42").iterdir()] == [f"p{phrase_id_of(5)}_tts.m4a"]


@pytest.mark.unit
def test_speech_for_a_phrase_changed_while_speaking_is_dropped(deps: dict) -> None:
    deps["job_phrases"].card.return_value = _make_candidate()
    deps["job_phrases"].holds.return_value = False
    deps["settings_repo"].get.return_value = None

    GenerateTTSUseCase(**deps).execute_one(PhraseRef(phrase_id_of(1), 0))

    deps["tts_repo"].upsert_for_phrase.assert_not_called()

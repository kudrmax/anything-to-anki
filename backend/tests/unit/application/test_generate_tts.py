from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.generate_tts import ALL_VOICES, GenerateTTSUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus


@pytest.fixture()
def deps(tmp_path: Path) -> dict:
    candidate_repo = MagicMock()
    tts_repo = MagicMock()
    tts_generator = MagicMock()
    settings_repo = MagicMock()
    media_root = str(tmp_path)
    return {
        "candidate_repo": candidate_repo,
        "tts_repo": tts_repo,
        "tts_generator": tts_generator,
        "settings_repo": settings_repo,
        "media_root": media_root,
    }


def _make_candidate(
    candidate_id: int = 1,
    source_id: int = 10,
    context_fragment: str = "She couldn't help but procrastinate.",
) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma="procrastinate",
        pos="VERB",
        status=CandidateStatus.LEARN,
        context_fragment=context_fragment,
        cefr_level=None,
        zipf_frequency=4.0,
        fragment_purity="clean",
        occurrences=1,
    )


@pytest.mark.unit
def test_generate_tts_calls_generator(deps: dict, tmp_path: Path) -> None:
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    deps["tts_generator"].generate_audio.assert_called_once()
    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][0] == "She couldn't help but procrastinate."
    assert str(call_args[0][1]).endswith("1_tts.m4a")
    assert call_args[0][2] in ALL_VOICES
    assert call_args[0][3] == 1.0

    deps["tts_repo"].upsert.assert_called_once()


@pytest.mark.unit
def test_generate_tts_respects_voice_setting(deps: dict) -> None:
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        '["bf_emma"]' if key == "tts_enabled_voices" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][2] == "bf_emma"


@pytest.mark.unit
def test_generate_tts_respects_speed_setting(deps: dict) -> None:
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        "0.8" if key == "tts_speed" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][3] == 0.8


@pytest.mark.unit
def test_generate_tts_skips_missing_candidate(deps: dict) -> None:
    deps["candidate_repo"].get_by_id.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(999)

    deps["tts_generator"].generate_audio.assert_not_called()
    deps["tts_repo"].upsert.assert_not_called()


@pytest.mark.unit
def test_execute_one_skips_empty_context_fragment(deps: dict) -> None:
    """When context_fragment is empty string, skip TTS generation."""
    candidate = _make_candidate(context_fragment="")
    deps["candidate_repo"].get_by_id.return_value = candidate

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    deps["tts_generator"].generate_audio.assert_not_called()
    deps["tts_repo"].upsert.assert_not_called()


@pytest.mark.unit
def test_execute_one_overwrites_existing_tts(deps: dict) -> None:
    """Upsert is called even if TTS already exists — overwrites with new path."""
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    # upsert is called — whether record existed or not, it's the repo's job
    deps["tts_repo"].upsert.assert_called_once()
    tts_entity = deps["tts_repo"].upsert.call_args[0][0]
    assert tts_entity.candidate_id == 1
    assert tts_entity.audio_path.endswith("1_tts.m4a")


@pytest.mark.unit
def test_pick_voice_with_empty_enabled_list_falls_back(deps: dict) -> None:
    """When enabled voices list is empty JSON array, fall back to ALL_VOICES."""
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        "[]" if key == "tts_enabled_voices" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][2] in ALL_VOICES


@pytest.mark.unit
def test_pick_voice_result_always_from_enabled_list(deps: dict) -> None:
    """When multiple voices enabled, picked voice is always from that list."""
    enabled = ["bf_emma", "am_adam", "af_heart"]
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        '["bf_emma", "am_adam", "af_heart"]' if key == "tts_enabled_voices" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    # Run multiple times to verify randomness stays within bounds
    for _ in range(20):
        use_case.execute_one(1)
        call_args = deps["tts_generator"].generate_audio.call_args
        assert call_args[0][2] in enabled


@pytest.mark.unit
def test_get_speed_with_invalid_string_falls_back_to_default(deps: dict) -> None:
    """Invalid speed string (e.g. 'abc') falls back to default 1.0."""
    candidate = _make_candidate()
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.side_effect = lambda key, *a: (
        "abc" if key == "tts_speed" else None
    )

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(1)

    call_args = deps["tts_generator"].generate_audio.call_args
    assert call_args[0][3] == 1.0


@pytest.mark.unit
def test_output_directory_created_under_media_root(deps: dict, tmp_path: Path) -> None:
    """Output directory is created based on source_id under media_root."""
    candidate = _make_candidate(candidate_id=5, source_id=42)
    deps["candidate_repo"].get_by_id.return_value = candidate
    deps["settings_repo"].get.return_value = None

    use_case = GenerateTTSUseCase(**deps)
    use_case.execute_one(5)

    call_args = deps["tts_generator"].generate_audio.call_args
    out_path = Path(str(call_args[0][1]))
    assert out_path.parent == tmp_path / "42"
    assert out_path.name == "5_tts.m4a"

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


def _make_candidate(candidate_id: int = 1, source_id: int = 10) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma="procrastinate",
        pos="VERB",
        status=CandidateStatus.LEARN,
        context_fragment="She couldn't help but procrastinate.",
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

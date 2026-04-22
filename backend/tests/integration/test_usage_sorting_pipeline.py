"""Integration test: usage_distribution storage and settings roundtrip."""
from __future__ import annotations

import json

import pytest
from backend.application.dto.settings_dtos import UpdateSettingsRequest
from backend.application.use_cases.manage_settings import ManageSettingsUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.models import StoredCandidateModel
from backend.infrastructure.persistence.sqla_settings_repository import (
    SqlaSettingsRepository,
)
from sqlalchemy.orm import Session


@pytest.mark.integration
class TestUsageSortingPipeline:
    def test_usage_distribution_stored_and_sorted(self, db_session: Session) -> None:
        """Settings roundtrip for usage_group_order."""
        settings_repo = SqlaSettingsRepository(db_session)
        settings_uc = ManageSettingsUseCase(settings_repo)
        custom_order = [
            "informal",
            "neutral",
            "formal",
            "specialized",
            "connotation",
            "old-fashioned",
            "offensive",
            "other",
        ]
        settings_uc.update_settings(
            UpdateSettingsRequest(usage_group_order=custom_order)
        )

        settings = settings_uc.get_settings()
        assert settings.usage_group_order == custom_order

        raw = settings_repo.get("usage_group_order")
        assert raw is not None
        assert json.loads(raw) == custom_order

    def test_usage_distribution_json_roundtrip(self, db_session: Session) -> None:
        """UsageDistribution survives DB serialize/deserialize."""
        candidate = StoredCandidate(
            source_id=1,
            lemma="cool",
            pos="JJ",
            cefr_level="B1",
            zipf_frequency=4.5,
            context_fragment="that's cool",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            usage_distribution=UsageDistribution({"neutral": 0.6, "informal": 0.4}),
        )
        model = StoredCandidateModel.from_entity(candidate)
        assert model.usage_distribution_json is not None

        restored = model.to_entity()
        assert restored.usage_distribution is not None
        assert restored.usage_distribution.groups == {"neutral": 0.6, "informal": 0.4}

    def test_null_usage_distribution_roundtrip(self, db_session: Session) -> None:
        """None usage_distribution -> NULL in DB -> None on entity."""
        candidate = StoredCandidate(
            source_id=1,
            lemma="unknown",
            pos="NN",
            cefr_level="B1",
            zipf_frequency=3.0,
            context_fragment="some context",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            usage_distribution=None,
        )
        model = StoredCandidateModel.from_entity(candidate)
        assert model.usage_distribution_json is None

        restored = model.to_entity()
        assert restored.usage_distribution is None

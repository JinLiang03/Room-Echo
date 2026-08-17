"""CalibrationProfile schema, checksum, and simulation guards."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from wifi_sensing.calibration import (
    CalibrationProfile,
    demo_profile,
    hard_invalidation_reasons,
    profile_match_score,
)
from wifi_sensing.config import FeatureConfig


def _profile() -> CalibrationProfile:
    return demo_profile(
        FeatureConfig(),
        "sha256:" + "a" * 64,
    )


def test_demo_profile_is_simulated_and_signed() -> None:
    profile = _profile()
    assert profile.simulated is True
    assert profile.verify_integrity()
    assert profile.checksum.startswith("sha256:")


def test_demo_cannot_be_presented_as_live() -> None:
    with pytest.raises(ValidationError, match="simulated"):
        CalibrationProfile.model_validate(
            {**_profile().model_dump(), "simulated": False}
        )


def test_tampered_profile_rejected() -> None:
    profile = _profile()
    tampered = CalibrationProfile.model_validate(
        {**profile.model_dump(), "room_id": "other_room"}
    )
    assert not tampered.verify_integrity()


def test_match_score_and_hard_invalidation() -> None:
    profile = _profile()
    score, mismatches = profile_match_score(
        profile,
        topology_hash="sha256:" + "b" * 64,  # different room/topology
        channel=profile.channel,
        bandwidth_mhz=profile.bandwidth_mhz,
        firmware_version=profile.firmware_version,
        feature_version=profile.feature_version,
    )
    assert "topology" in mismatches
    assert score < 1.0
    assert hard_invalidation_reasons(
        profile,
        topology_hash="sha256:" + "b" * 64,
        channel=profile.channel,
        bandwidth_mhz=profile.bandwidth_mhz,
        firmware_version=profile.firmware_version,
        feature_version=profile.feature_version,
    ) == ["topology"]


def test_channel_firmware_feature_changes_are_hard() -> None:
    profile = _profile()
    reasons = hard_invalidation_reasons(
        profile,
        topology_hash=profile.topology_hash,
        channel=11,
        bandwidth_mhz=profile.bandwidth_mhz,
        firmware_version="other-fw",
        feature_version="features-v9",
    )
    assert set(reasons) == {"channel", "firmware", "feature_version"}

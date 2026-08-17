"""Deterministic sensing pipeline (Phases 04-06): features and proxy signals."""

from __future__ import annotations

from .calibration import CalibrationProfile, demo_profile, fit_profile
from .config import FeatureConfig
from .pipeline import FeaturePipeline

__version__ = "0.1.0"

__all__ = [
    "CalibrationProfile",
    "FeatureConfig",
    "FeaturePipeline",
    "__version__",
    "demo_profile",
    "fit_profile",
]

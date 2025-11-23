"""
Quality validation framework for Marker OCR

This module provides comprehensive quality assessment for OCR extraction,
including pre-checks, post-validation, comparison, and learning capabilities.
"""

from marker.quality.validator import QualityValidator, ExtractionQualityMetrics, ValidationResult
from marker.quality.predictor import QualityPredictor, Prediction
from marker.quality.comparator import ExtractionComparator, ComparisonResult
from marker.quality.learner import QualityLearner
from marker.quality.reporter import QualityReporter, Report

__all__ = [
    "QualityValidator",
    "ExtractionQualityMetrics",
    "ValidationResult",
    "QualityPredictor",
    "Prediction",
    "ExtractionComparator",
    "ComparisonResult",
    "QualityLearner",
    "QualityReporter",
    "Report",
]

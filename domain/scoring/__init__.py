"""Validated scoring engines."""

from .badminton import (
    BadmintonProfile,
    BadmintonScoreValidation,
    validate_match_score as validate_badminton_score,
)
from .padel import (
    PadelProfile,
    PadelScoreValidation,
    PointSplitValidation,
    validate_match_score as validate_padel_score,
    validate_point_split_score,
)
from .registry import RuleProfile, UnsupportedScoringProfile, validate_score
from .table_tennis import ScoreValidation, validate_match_score

__all__ = [
    "BadmintonProfile",
    "BadmintonScoreValidation",
    "PadelProfile",
    "PadelScoreValidation",
    "PointSplitValidation",
    "RuleProfile",
    "ScoreValidation",
    "UnsupportedScoringProfile",
    "validate_badminton_score",
    "validate_match_score",
    "validate_padel_score",
    "validate_point_split_score",
    "validate_score",
]

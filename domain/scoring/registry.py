"""Select a validated scoring engine from an immutable rule profile."""

from dataclasses import dataclass

from .badminton import BadmintonProfile, validate_match_score as validate_badminton
from .padel import PadelProfile, validate_match_score as validate_padel
from .table_tennis import validate_match_score as validate_table_tennis


@dataclass(frozen=True)
class RuleProfile:
    sport_key: str
    profile_key: str
    version: int
    config: dict


class UnsupportedScoringProfile(ValueError):
    pass


def validate_score(profile: RuleProfile, segments):
    if profile.version < 1:
        raise UnsupportedScoringProfile("Rule profile version must be positive.")
    config = profile.config

    if profile.sport_key == "table-tennis":
        try:
            return validate_table_tennis(
                segments,
                best_of=int(config["best_of"]),
                points_to_win=int(config.get("points_to_win", 11)),
                win_by=int(config.get("win_by", 2)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise UnsupportedScoringProfile(
                f"Invalid Table Tennis profile {profile.profile_key} v{profile.version}."
            ) from exc

    if profile.sport_key == "badminton":
        try:
            decider_points_to_win = config.get("decider_points_to_win")
            decider_win_by = config.get("decider_win_by")
            decider_point_cap = config.get("decider_point_cap")
            badminton_profile = BadmintonProfile(
                profile_key=profile.profile_key,
                version=profile.version,
                best_of=int(config["best_of"]),
                points_to_win=int(config["points_to_win"]),
                win_by=int(config["win_by"]),
                point_cap=int(config["point_cap"]),
                decider_points_to_win=int(decider_points_to_win) if decider_points_to_win is not None else None,
                decider_win_by=int(decider_win_by) if decider_win_by is not None else None,
                decider_point_cap=int(decider_point_cap) if decider_point_cap is not None else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise UnsupportedScoringProfile(
                f"Invalid Badminton profile {profile.profile_key} v{profile.version}."
            ) from exc
        return validate_badminton(segments, badminton_profile)

    if profile.sport_key == "padel":
        tie_break_at = config.get("tie_break_at", "6-6")
        if tie_break_at not in ("6-6", None, False):
            raise UnsupportedScoringProfile(
                f"Unsupported Padel tie-break trigger: {tie_break_at!r}."
            )
        try:
            padel_profile = PadelProfile(
                profile_key=profile.profile_key,
                version=profile.version,
                best_of=int(config["best_of"]),
                games_to_win_set=int(config.get("games_to_win_set", 6)),
                set_win_by=int(config.get("set_win_by", 2)),
                tie_break_at_six_all=bool(tie_break_at),
                game_scoring_method=config.get("game_scoring_method", "advantage"),
                deciding_set_policy=config.get("deciding_set_policy", "standard"),
                match_tiebreak_target=int(config.get("match_tiebreak_target", 10)),
                match_tiebreak_win_by=int(config.get("match_tiebreak_win_by", 2)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise UnsupportedScoringProfile(
                f"Invalid Padel profile {profile.profile_key} v{profile.version}."
            ) from exc
        return validate_padel(segments, padel_profile)

    raise UnsupportedScoringProfile(
        f"No scoring engine is registered for sport {profile.sport_key!r}."
    )

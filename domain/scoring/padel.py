"""Padel set validation for standard and deciding-match-tie-break profiles."""

from dataclasses import dataclass
from typing import Literal, Sequence


WinnerSide = Literal["a", "b"]
GameScoringMethod = Literal["advantage", "golden_point", "star_point"]
DecidingSetPolicy = Literal["standard", "match_tiebreak"]


@dataclass(frozen=True)
class PadelProfile:
    profile_key: str = "padel-standard-advantage"
    version: int = 1
    best_of: int = 3
    games_to_win_set: int = 6
    set_win_by: int = 2
    tie_break_at_six_all: bool = True
    game_scoring_method: GameScoringMethod = "advantage"
    deciding_set_policy: DecidingSetPolicy = "standard"
    match_tiebreak_target: int = 10
    match_tiebreak_win_by: int = 2


@dataclass(frozen=True)
class PadelScoreValidation:
    errors: tuple[str, ...]
    sets_won_a: int
    sets_won_b: int
    sets_needed: int
    winner_side: WinnerSide | None

    @property
    def is_valid(self):
        return not self.errors

    @property
    def is_complete(self):
        return self.is_valid and self.winner_side is not None


DEFAULT_PROFILE = PadelProfile()


def _profile_errors(profile):
    errors = []
    if profile.version < 1 or profile.best_of < 1 or profile.best_of % 2 == 0:
        errors.append("Profil Padel harus memiliki versi positif dan format Best of ganjil.")
    if profile.games_to_win_set < 1 or profile.set_win_by < 1:
        errors.append("Target game dan margin set Padel harus positif.")
    if profile.game_scoring_method not in {"advantage", "golden_point", "star_point"}:
        errors.append("Metode skor game Padel tidak didukung.")
    if profile.deciding_set_policy not in {"standard", "match_tiebreak"}:
        errors.append("Kebijakan deciding set Padel tidak didukung.")
    if profile.match_tiebreak_target < 1 or profile.match_tiebreak_win_by < 1:
        errors.append("Profil match tie-break Padel tidak valid.")
    return errors


def _standard_set_is_complete(score_a, score_b, profile):
    high, low = max(score_a, score_b), min(score_a, score_b)
    target = profile.games_to_win_set
    win_by = profile.set_win_by

    if high < target:
        return False
    if low < target - 1:
        return high == target and high - low >= win_by
    if profile.tie_break_at_six_all:
        return high == target + 1 and low in (target - 1, target)
    return high - low == win_by


def _match_tiebreak_is_complete(score_a, score_b, profile):
    high, low = max(score_a, score_b), min(score_a, score_b)
    target = profile.match_tiebreak_target
    win_by = profile.match_tiebreak_win_by
    if high < target or high - low < win_by:
        return False
    if low >= target - 1:
        return high - low == win_by
    return high == target


def validate_match_score(
    sets: Sequence[Sequence[int]], profile: PadelProfile = DEFAULT_PROFILE
):
    errors = _profile_errors(profile)
    sets_needed = profile.best_of // 2 + 1
    won_a = 0
    won_b = 0

    if len(sets) > profile.best_of:
        errors.append(
            f"Maksimal {profile.best_of} set untuk pertandingan Best of {profile.best_of}."
        )

    for index, segment in enumerate(sets, start=1):
        if won_a >= sets_needed or won_b >= sets_needed:
            errors.append(f"Set {index} tidak boleh diisi karena pertandingan sudah selesai.")
            break
        if (
            not isinstance(segment, (list, tuple))
            or len(segment) != 2
            or any(not isinstance(value, int) or isinstance(value, bool) for value in segment)
        ):
            errors.append(f"Skor set {index} harus berisi dua bilangan bulat.")
            continue
        score_a, score_b = segment
        if score_a < 0 or score_b < 0:
            errors.append(f"Skor set {index} tidak boleh negatif.")
            continue
        if score_a == score_b:
            errors.append(f"Skor set {index} tidak boleh seri.")
            continue

        is_deciding_match_tiebreak = (
            profile.deciding_set_policy == "match_tiebreak"
            and index == profile.best_of
            and won_a == sets_needed - 1
            and won_b == sets_needed - 1
        )
        is_complete = (
            _match_tiebreak_is_complete(score_a, score_b, profile)
            if is_deciding_match_tiebreak
            else _standard_set_is_complete(score_a, score_b, profile)
        )
        if not is_complete:
            unit = "match tie-break" if is_deciding_match_tiebreak else "set"
            errors.append(
                f"{unit.capitalize()} {index} belum memiliki skor akhir yang sah untuk "
                f"profil {profile.profile_key} v{profile.version}."
            )
            continue
        if score_a > score_b:
            won_a += 1
        else:
            won_b += 1

    winner_side = None
    if not errors:
        if won_a == sets_needed:
            winner_side = "a"
        elif won_b == sets_needed:
            winner_side = "b"
    return PadelScoreValidation(
        errors=tuple(errors),
        sets_won_a=won_a,
        sets_won_b=won_b,
        sets_needed=sets_needed,
        winner_side=winner_side,
    )

"""Validated Badminton game scoring with versionable profile parameters."""

from dataclasses import dataclass
from typing import Literal, Sequence


WinnerSide = Literal["a", "b"]


@dataclass(frozen=True)
class BadmintonProfile:
    profile_key: str = "badminton-21-bo3"
    version: int = 1
    best_of: int = 3
    points_to_win: int = 21
    win_by: int = 2
    point_cap: int = 30
    # Optional override for the rubber/deciding game (the last possible game
    # in the series, e.g. game 3 of a Best-of-3) -- some tournaments shorten
    # it to a sudden-victory race instead of the full 21-point deuce game.
    decider_points_to_win: int | None = None
    decider_win_by: int | None = None
    decider_point_cap: int | None = None


@dataclass(frozen=True)
class BadmintonScoreValidation:
    errors: tuple[str, ...]
    games_won_a: int
    games_won_b: int
    games_needed: int
    winner_side: WinnerSide | None

    @property
    def is_valid(self):
        return not self.errors

    @property
    def is_complete(self):
        return self.is_valid and self.winner_side is not None


DEFAULT_PROFILE = BadmintonProfile()


def _profile_errors(profile):
    errors = []
    if profile.version < 1 or profile.best_of < 1 or profile.best_of % 2 == 0:
        errors.append("Profil Badminton harus memiliki versi positif dan format Best of ganjil.")
    if profile.points_to_win < 1 or profile.win_by < 1:
        errors.append("Target poin dan margin kemenangan Badminton harus positif.")
    if profile.point_cap < profile.points_to_win:
        errors.append("Batas poin Badminton tidak boleh di bawah target game.")
    decider_fields = (
        profile.decider_points_to_win,
        profile.decider_win_by,
        profile.decider_point_cap,
    )
    if any(value is not None for value in decider_fields):
        if not all(value is not None for value in decider_fields):
            errors.append("Profil game rubber Badminton harus mengisi target, margin, dan batas poin sekaligus.")
        elif profile.decider_points_to_win < 1 or profile.decider_win_by < 1:
            errors.append("Target poin dan margin kemenangan game rubber Badminton harus positif.")
        elif profile.decider_point_cap < profile.decider_points_to_win:
            errors.append("Batas poin game rubber Badminton tidak boleh di bawah target game.")
    return errors


def _game_is_complete(score_a, score_b, target, win_by, cap):
    high, low = max(score_a, score_b), min(score_a, score_b)

    if high > cap or high < target:
        return False
    if low < target - 1:
        return high == target and high - low >= win_by
    if high == cap:
        # At the cap, either the normal margin was achieved (30-28 in the
        # standard profile) or the cap itself decides a 29-all game (30-29).
        return high - low in (win_by, 1)
    return high - low == win_by


def validate_match_score(
    games: Sequence[Sequence[int]], profile: BadmintonProfile = DEFAULT_PROFILE
):
    errors = _profile_errors(profile)
    games_needed = profile.best_of // 2 + 1
    won_a = 0
    won_b = 0

    if len(games) > profile.best_of:
        errors.append(
            f"Maksimal {profile.best_of} game untuk pertandingan Best of {profile.best_of}."
        )

    for index, game in enumerate(games, start=1):
        if won_a >= games_needed or won_b >= games_needed:
            errors.append(f"Game {index} tidak boleh diisi karena pertandingan sudah selesai.")
            break
        if (
            not isinstance(game, (list, tuple))
            or len(game) != 2
            or any(not isinstance(value, int) or isinstance(value, bool) for value in game)
        ):
            errors.append(f"Skor game {index} harus berisi dua bilangan bulat.")
            continue
        score_a, score_b = game
        if score_a < 0 or score_b < 0:
            errors.append(f"Skor game {index} tidak boleh negatif.")
            continue
        if score_a == score_b:
            errors.append(f"Skor game {index} tidak boleh seri.")
            continue
        is_decider = index == profile.best_of and profile.decider_points_to_win is not None
        target = profile.decider_points_to_win if is_decider else profile.points_to_win
        win_by = profile.decider_win_by if is_decider else profile.win_by
        cap = profile.decider_point_cap if is_decider else profile.point_cap
        if not _game_is_complete(score_a, score_b, target, win_by, cap):
            errors.append(
                f"Game {index} belum memiliki skor akhir yang sah untuk profil "
                f"{profile.profile_key} v{profile.version}."
            )
            continue
        if score_a > score_b:
            won_a += 1
        else:
            won_b += 1

    winner_side = None
    if not errors:
        if won_a == games_needed:
            winner_side = "a"
        elif won_b == games_needed:
            winner_side = "b"
    return BadmintonScoreValidation(
        errors=tuple(errors),
        games_won_a=won_a,
        games_won_b=won_b,
        games_needed=games_needed,
        winner_side=winner_side,
    )

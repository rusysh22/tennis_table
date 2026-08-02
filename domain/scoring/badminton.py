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
    return errors


def _game_is_complete(score_a, score_b, profile):
    high, low = max(score_a, score_b), min(score_a, score_b)
    target = profile.points_to_win
    cap = profile.point_cap
    win_by = profile.win_by

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
        if not _game_is_complete(score_a, score_b, profile):
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

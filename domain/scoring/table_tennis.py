"""Table Tennis score validation.

The web UI currently records completed games rather than individual points.  This
module deliberately has no Flask or persistence dependencies so it can also be
used by a future score-event API.
"""

from dataclasses import dataclass
from typing import Literal, Sequence


WinnerSide = Literal["a", "b"]


@dataclass(frozen=True)
class ScoreValidation:
    errors: tuple[str, ...]
    games_won_a: int
    games_won_b: int
    games_needed: int
    winner_side: WinnerSide | None

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def is_complete(self) -> bool:
        return self.is_valid and self.winner_side is not None


def _game_is_complete(score_a: int, score_b: int, target: int, win_by: int) -> bool:
    high, low = max(score_a, score_b), min(score_a, score_b)
    if high < target or high - low < win_by:
        return False
    if low < target - 1:
        # Before deuce the game must stop exactly when the winner reaches the
        # target. Scores such as 21-9 are not attainable in an 11-point game.
        return high == target
    # Once both sides reach target - 1, play stops at the first win-by margin.
    return high - low == win_by


def validate_match_score(
    games: Sequence[Sequence[int]],
    *,
    best_of: int = 3,
    points_to_win: int = 11,
    win_by: int = 2,
) -> ScoreValidation:
    """Validate a sequence of completed Table Tennis games.

    Supports the event's Best-of-3 and Best-of-5 profiles, including uncapped
    deuce. Empty score entry is valid but represents an incomplete match.
    """
    errors: list[str] = []
    if best_of not in (3, 5):
        errors.append("Profil pertandingan harus Best of 3 atau Best of 5.")
    if points_to_win < 1 or win_by < 1:
        errors.append("Profil skor pertandingan tidak valid.")

    games_needed = best_of // 2 + 1 if best_of > 0 else 0
    won_a = 0
    won_b = 0

    if len(games) > best_of:
        errors.append(f"Maksimal {best_of} game untuk pertandingan Best of {best_of}.")

    for index, game in enumerate(games, start=1):
        if won_a >= games_needed or won_b >= games_needed:
            errors.append(
                f"Game {index} tidak boleh diisi karena pertandingan sudah selesai."
            )
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
        if not _game_is_complete(score_a, score_b, points_to_win, win_by):
            errors.append(
                f"Game {index} belum memiliki skor akhir yang sah "
                f"(minimal {points_to_win} poin dan menang selisih {win_by})."
            )
            continue

        if score_a > score_b:
            won_a += 1
        else:
            won_b += 1

    winner_side: WinnerSide | None = None
    if not errors:
        if won_a == games_needed:
            winner_side = "a"
        elif won_b == games_needed:
            winner_side = "b"

    return ScoreValidation(
        errors=tuple(errors),
        games_won_a=won_a,
        games_won_b=won_b,
        games_needed=games_needed,
        winner_side=winner_side,
    )

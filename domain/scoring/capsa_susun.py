"""Validated Capsa Susun (13-card climbing game) round-based scoring.

A Capsa Susun match at one table is 5 rounds between two pairs (4 players).
Each round ends when one player empties their hand; every other player's
remaining cards convert to points via a multiplier that grows with the
count still held. Points accumulate across all 5 rounds and, unlike rally
sports, the pair with the LOWER total wins the match.
"""

from dataclasses import dataclass
from typing import Literal, Sequence

WinnerSide = Literal["a", "b"]

ROUNDS_PER_MATCH = 5
MAX_CARDS_PER_HAND = 13


@dataclass(frozen=True)
class CapsaScoreValidation:
    errors: tuple[str, ...]
    points_a: int
    points_b: int
    rounds_played: int
    winner_side: WinnerSide | None

    @property
    def is_valid(self):
        return not self.errors

    @property
    def is_complete(self):
        return self.is_valid and self.winner_side is not None


def card_multiplier(remaining_cards):
    """Base multiplier for a player's remaining card count at round end."""
    if remaining_cards <= 0:
        return 0
    if remaining_cards <= 9:
        return 1
    if remaining_cards <= 12:
        return 2
    return 3


def player_points(remaining_cards, twos_remaining=0):
    """Points for one player at round end: remaining x multiplier, doubled
    again for each '2' card still held."""
    if remaining_cards <= 0:
        return 0
    multiplier = card_multiplier(remaining_cards) * (2 ** max(0, int(twos_remaining)))
    return int(remaining_cards) * multiplier


def round_points(a1, a2, b1, b2, a1_twos=0, a2_twos=0, b1_twos=0, b2_twos=0):
    """Aggregate one round's per-player remaining cards into pair totals."""
    points_a = player_points(a1, a1_twos) + player_points(a2, a2_twos)
    points_b = player_points(b1, b1_twos) + player_points(b2, b2_twos)
    return points_a, points_b


def validate_round_hand(a1, a2, b1, b2):
    """Sanity-check one round's raw remaining-card counts (0-13, and
    exactly one player must have gone out for the round to be complete)."""
    errors = []
    values = {"A1": a1, "A2": a2, "B1": b1, "B2": b2}
    for label, value in values.items():
        if value is None:
            errors.append(f"Sisa kartu {label} belum diisi.")
        elif not (0 <= value <= MAX_CARDS_PER_HAND):
            errors.append(f"Sisa kartu {label} harus antara 0 dan {MAX_CARDS_PER_HAND}.")
    if not errors and not any(v == 0 for v in values.values()):
        errors.append("Salah satu pemain harus menghabiskan kartu (sisa 0) agar ronde selesai.")
    return errors


def validate_match_score(segments: Sequence[Sequence[int]]):
    """segments: list of up to 5 [points_a, points_b] round totals.
    The pair with the lower 5-round total wins."""
    errors = []
    if len(segments) > ROUNDS_PER_MATCH:
        errors.append(f"Capsa Banting maksimal {ROUNDS_PER_MATCH} ronde per match.")

    for index, seg in enumerate(segments, start=1):
        if len(seg) != 2:
            errors.append(f"Data ronde {index} tidak valid.")
            continue
        a, b = seg
        if a < 0 or b < 0:
            errors.append(f"Poin ronde {index} tidak boleh negatif.")

    points_a = sum(seg[0] for seg in segments if len(seg) == 2)
    points_b = sum(seg[1] for seg in segments if len(seg) == 2)
    rounds_played = len(segments)

    winner_side = None
    if not errors and rounds_played == ROUNDS_PER_MATCH:
        if points_a == points_b:
            errors.append(
                "Total poin kedua pasangan sama persis — tidak boleh seri, cek ulang perhitungan tiap ronde."
            )
        else:
            winner_side = "a" if points_a < points_b else "b"

    return CapsaScoreValidation(
        errors=tuple(errors),
        points_a=points_a,
        points_b=points_b,
        rounds_played=rounds_played,
        winner_side=winner_side,
    )

"""Pure calculation functions — no DB, no Flask, fully unit-testable.

White Paper §5.1 (definitions) and §9 (sets.tut_sec).
"""


def brzycki_e1rm(weight_kg: float, reps: int) -> float | None:
    """Estimated 1RM via the Brzycki formula (BR-07: only valid for reps <= 10)."""
    if reps is None or reps <= 0 or reps > 10:
        return None
    if reps == 1:
        return round(weight_kg, 2)
    return round(weight_kg * 36 / (37 - reps), 2)


def tonnage(weight_kg: float, reps: int) -> float:
    """Total work for one set: weight x reps."""
    return round(weight_kg * reps, 2)


def round_to_plate(weight_kg: float, unit: str = "kg") -> float:
    """Rounds a recommended weight to the smallest realistic increment
    (White Paper §5.4): 2.5 kg for barbell work, 2 kg for dumbbell steps.
    """
    step = 2.0 if unit == "db" else 2.5
    return round(round(weight_kg / step) * step, 2)


def tut_sec(reps: int, tempo: str | None) -> int | None:
    """Time under tension: reps x sum of the four tempo digits (E-P-C-P format).
    e.g. reps=8, tempo="2-0-1-0" -> 8 * (2+0+1+0) = 24 seconds.
    """
    if not tempo or not reps:
        return None
    try:
        parts = [int(p) for p in tempo.split("-")]
    except ValueError:
        return None
    if len(parts) != 4:
        return None
    return reps * sum(parts)


def weight_jump_is_suspicious(new_weight: float, previous_weight: float | None) -> bool:
    """Outlier check (White Paper §5.9 / BR-03): a jump of more than +20%
    versus the previous session is flagged as a possible typo in the UI.
    """
    if not previous_weight or previous_weight <= 0:
        return False
    return new_weight > previous_weight * 1.20

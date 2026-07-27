"""
engine/warning_detector.py
----------------------------
Generates the dashboard's warning cards (White Paper §14, BR-09).

Design mirrors predictor.py: pure functions, no DB/Flask imports, so
every detector is unit-testable in isolation. api/analytics.py fetches
the data each detector needs and calls detect_warnings() once per
dashboard load; it owns persistence/dedupe (Warning rows, 7-day dismiss
suppression) since that's inherently stateful.

Each detector inspects one narrow signal and returns a WarningCandidate
or None. detect_warnings() collects every non-None result, sorts by
priority (lower = more urgent), and the caller keeps at most 3 (BR-09).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from engine.formulas import weight_jump_is_suspicious
from engine.predictor import (
    SessionLog,
    deload_streak_triggered,
    regression_slope_over_days,
    STALE_SESSION_DAYS,
)

# ---------------------------------------------------------------------------
# Thresholds — kept local since this module is the only consumer, same
# convention predictor.py uses for its own constants.
# ---------------------------------------------------------------------------

PLATEAU_MIN_SESSIONS = 5                  # BR-06 regression floor
PLATEAU_SLOPE_KG_PER_WEEK = 0.0           # flat-or-declining e1RM trend
MUSCLE_IMBALANCE_WINDOW_DAYS = 14
MUSCLE_IMBALANCE_RATIO = 3.0              # busiest group >= 3x the quietest
MUSCLE_IMBALANCE_MIN_SETS = 4             # ignore near-empty groups (noise)
INACTIVITY_GRACE_DAYS = 2                 # beyond the user's own cadence
GOAL_MISMATCH_MIN_SETS = 10               # need enough sets to trust the mix
GOAL_MISMATCH_SHARE = 0.6                 # >=60% of sets outside goal's range

# Lower number = shown first when more than 3 warnings are active (BR-09).
# White Paper §15 orders warning categories overreaching > deload > plateau
# > frequentie > overig; deload_needed is this codebase's single detector
# for both (a 3-session RPE>=9 streak is the overreaching signal that
# triggers the deload recommendation), muscle_imbalance is the frequency/
# distribution check, and the remaining, lower-severity detectors fill the
# "overig" tier, ordered by how actionable/severe they are.
PRIORITY = {
    "deload_needed": 1,
    "plateau": 2,
    "muscle_imbalance": 3,
    "suspicious_jump": 4,
    "goal_mismatch": 5,
    "stale_exercise": 6,
    "inactivity": 7,
}


@dataclass
class WarningCandidate:
    warning_type: str
    message: str
    action_hint: str
    severity: str  # "high" | "medium" | "low"

    @property
    def priority(self) -> int:
        return PRIORITY[self.warning_type]


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def detect_deload_needed(exercise_histories: dict[int, tuple[str, list[SessionLog]]]) -> WarningCandidate | None:
    """BR-04: 3 consecutive sessions at RPE >= 9 on any trained exercise."""
    for _, (name, sessions) in exercise_histories.items():
        if deload_streak_triggered(sessions):
            return WarningCandidate(
                warning_type="deload_needed",
                message=f"RPE was 3 sessies op rij hoog bij {name}.",
                action_hint="Plan een deload-week in: -35% belasting en -1 set per oefening.",
                severity="high",
            )
    return None


def detect_suspicious_jump(exercise_histories: dict[int, tuple[str, list[SessionLog]]]) -> WarningCandidate | None:
    """A working weight >20% above the previous session — likely a typo (§5.9)."""
    for _, (name, sessions) in exercise_histories.items():
        if len(sessions) < 2:
            continue
        previous, latest = sessions[-2], sessions[-1]
        prev_top = previous.best_set()
        latest_top = latest.best_set()
        if not prev_top or not latest_top:
            continue
        if weight_jump_is_suspicious(latest_top.weight_kg, prev_top.weight_kg):
            return WarningCandidate(
                warning_type="suspicious_jump",
                message=f"{name}: {latest_top.weight_kg:g} kg is een grote sprong t.o.v. {prev_top.weight_kg:g} kg vorige keer.",
                action_hint="Controleer of het gewicht klopt — pas de set aan als het een tikfout was.",
                severity="medium",
            )
    return None


def detect_plateau(exercise_histories: dict[int, tuple[str, list[SessionLog]]], as_of: date) -> WarningCandidate | None:
    """BR-06: e1RM trend flat-or-declining over the last 5+ sessions."""
    for _, (name, sessions) in exercise_histories.items():
        if len(sessions) < PLATEAU_MIN_SESSIONS:
            continue
        dated = [
            ((s.performed_at - as_of).days, e1rm)
            for s in sessions
            if (e1rm := s.e1rm()) is not None
        ]
        if len(dated) < PLATEAU_MIN_SESSIONS:
            continue
        slope_per_day = regression_slope_over_days(dated)
        if slope_per_day is None:
            continue
        slope_per_week = slope_per_day * 7
        if slope_per_week <= PLATEAU_SLOPE_KG_PER_WEEK:
            return WarningCandidate(
                warning_type="plateau",
                message=f"{name} laat al {len(dated)} sessies geen vooruitgang meer zien.",
                action_hint="Overweeg een variant, een deload, of extra herstel deze week.",
                severity="medium",
            )
    return None


def detect_muscle_imbalance(muscle_group_sets: dict[str, int]) -> WarningCandidate | None:
    """Trailing-window set counts (§5.5's frequency logic) skewed heavily
    toward one muscle group vs. the rest — the classic "arm day every
    day" pattern."""
    trained = {g: n for g, n in muscle_group_sets.items() if n > 0}
    if len(trained) < 2:
        return None
    busiest_group, busiest = max(trained.items(), key=lambda kv: kv[1])
    quietest_group, quietest = min(trained.items(), key=lambda kv: kv[1])
    if busiest < MUSCLE_IMBALANCE_MIN_SETS:
        return None
    if quietest == 0 or busiest / quietest >= MUSCLE_IMBALANCE_RATIO:
        return WarningCandidate(
            warning_type="muscle_imbalance",
            message=f"{busiest_group.capitalize()} kreeg veel meer volume dan {quietest_group} de afgelopen 2 weken.",
            action_hint=f"Plan een sessie met focus op {quietest_group} om de balans te herstellen.",
            severity="low",
        )
    return None


def detect_goal_mismatch(goal: str, rep_counts: list[int]) -> WarningCandidate | None:
    """Actual rep ranges drifting away from what the stated goal calls
    for — e.g. a strength-goal user mostly doing 15+ rep sets."""
    if len(rep_counts) < GOAL_MISMATCH_MIN_SETS:
        return None
    if goal == "strength":
        out_of_range = sum(1 for r in rep_counts if r > 8)
        target_desc, actual_desc = "lage reps (1-6)", "veel sets boven de 8 reps"
    else:
        out_of_range = sum(1 for r in rep_counts if r > 20)
        target_desc, actual_desc = "hypertrofie-reps (6-15)", "veel sets met 20+ reps"
    if out_of_range / len(rep_counts) >= GOAL_MISMATCH_SHARE:
        return WarningCandidate(
            warning_type="goal_mismatch",
            message=f"Je traint vooral {actual_desc}, terwijl je doel {target_desc} vraagt.",
            action_hint="Check of je rep-ranges nog passen bij je doel in Instellingen.",
            severity="low",
        )
    return None


def detect_stale_exercise(exercise_histories: dict[int, tuple[str, list[SessionLog]]], as_of: date) -> WarningCandidate | None:
    """§5.9: an exercise the user used to train regularly, untouched for
    90+ days — the detraining risk the WOD generator already discounts
    silently; surface it explicitly here."""
    for _, (name, sessions) in exercise_histories.items():
        if len(sessions) < 3:
            continue  # "used to train regularly" needs some track record
        last_trained = max(s.performed_at for s in sessions)
        days_since = (as_of - last_trained).days
        if days_since >= STALE_SESSION_DAYS:
            return WarningCandidate(
                warning_type="stale_exercise",
                message=f"{name} is {days_since} dagen niet getraind — voortgang telt niet meer mee.",
                action_hint="Bouw het rustig weer op als je het wilt hervatten.",
                severity="low",
            )
    return None


def detect_inactivity(last_workout_date: date | None, as_of: date, days_per_week: int | None) -> WarningCandidate | None:
    """No logged workout for longer than the user's own cadence implies."""
    expected_gap_days = round(7 / (days_per_week or 3))
    allowed_gap = expected_gap_days + INACTIVITY_GRACE_DAYS
    if last_workout_date is None:
        return WarningCandidate(
            warning_type="inactivity",
            message="Je hebt nog geen workout gelogd.",
            action_hint="Log je eerste workout om aanbevelingen op maat te krijgen.",
            severity="low",
        )
    days_since = (as_of - last_workout_date).days
    if days_since > allowed_gap:
        return WarningCandidate(
            warning_type="inactivity",
            message=f"Je laatste workout was {days_since} dagen geleden.",
            action_hint="Kies een korte sessie om de draad weer op te pakken.",
            severity="low",
        )
    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def detect_warnings(
    *,
    goal: str,
    exercise_histories: dict[int, tuple[str, list[SessionLog]]],
    muscle_group_sets: dict[str, int],
    rep_counts: list[int],
    last_workout_date: date | None,
    days_per_week: int | None,
    as_of: date | None = None,
) -> list[WarningCandidate]:
    """Runs every detector and returns all triggered candidates, sorted
    most-urgent first. Caller (api/analytics.py) handles persistence,
    the 7-day dismiss window, and truncating to 3 (BR-09)."""
    as_of = as_of or date.today()
    candidates = [
        detect_deload_needed(exercise_histories),
        detect_suspicious_jump(exercise_histories),
        detect_plateau(exercise_histories, as_of),
        detect_muscle_imbalance(muscle_group_sets),
        detect_goal_mismatch(goal, rep_counts),
        detect_stale_exercise(exercise_histories, as_of),
        detect_inactivity(last_workout_date, as_of, days_per_week),
    ]
    triggered = [c for c in candidates if c is not None]
    triggered.sort(key=lambda c: c.priority)
    return triggered

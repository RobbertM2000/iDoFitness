"""
engine/predictor.py
--------------------
Per-exercise recommendation engine.
White Paper references: §5.3 (hypertrophy), §5.4 (strength), §5.7 (regression),
§5.8 (cold start), §5.9 (outliers/staleness), §8.1-8.2/8.4/8.8/8.9 (progression
methods, recovery, experience dispatch).

Design: pure functions (history + profile in, Advice out). No database access,
no Flask imports — every code path is unit-testable in isolation, per the white
paper's own instruction in §5.9's implementation summary ("implementeer
predictor.py met pure functies... zodat alles unit-testbaar is zonder database").

Business rules enforced here:
  BR-01  Every Advice carries a human-readable `reason`.
  BR-02  global_goal has exactly two values; every goal branch is explicit
         (see get_recommendation's dispatch + the ValueError guard).
  BR-03  A weight recommendation never deviates >5% from the last working
         weight (see clamp_weight_change; deliberately NOT applied to deloads,
         which are supposed to be a large, intentional drop).
  BR-04  RPE >= 9 for 3 consecutive sessions -> deload advice, never an
         increase. Applies to all three strategies (hypertrophy, strength,
         beginner-linear), not just strength.
  BR-06  Regression requires >=5 data points; below that, no trend is
         reported (None), and callers fall back to rule-based logic only.
  BR-07  e1RM is only computed from sets with reps <= 10 (Brzycki validity).
  BR-08  Warmup sets never influence tonnage, e1RM, or recommendations
         (SessionLog.working_sets() filters them out at the source).

NOTE on duplication: this file intentionally defines its own `brzycki()` and
`round_to_plate()` rather than importing from engine/formulas.py, because this
module needs to be drop-in testable without assuming that file's exact current
contents. Session #5 already added a Brzycki implementation to formulas.py —
if its signature matches (weight_kg, reps) -> float | None, delete the two
functions below and import from formulas instead so there's one canonical
copy. See PREDICTOR_INTEGRATION.md for the exact steps.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from sklearn.linear_model import LinearRegression
import numpy as np


# ---------------------------------------------------------------------------
# Constants — thresholds live here so tuning never requires touching logic.
# Mirrors the white paper's own advice (ch. 14 summary: "alle drempels als
# constanten in één thresholds.py"); kept local to this module for now since
# predictor.py is the only consumer. Move into engine/thresholds.py alongside
# warning_detector.py in the next session if the warning detector wants to
# share any of these.
# ---------------------------------------------------------------------------

COLD_START_MIN_SESSIONS = 5              # §5.8 — below this: "provisional"
REGRESSION_MIN_POINTS = 5                # BR-06
STALE_SESSION_DAYS = 90                  # §5.9 — sessions older than this don't count
OUTLIER_MAX_REPS = 30                    # §5.9 — ignore sets with reps > 30
MAX_WEIGHT_DEVIATION_PCT = 0.05          # BR-03

RPE_CONSOLIDATE_THRESHOLD = 9.5          # hypertrophy: >= this -> repeat session
RPE_FAST_TRACK_THRESHOLD = 6.0           # hypertrophy: <= this at ceiling -> +5%
RPE_HOLD_THRESHOLD = 9.0                 # strength: >= this -> hold, don't push
DELOAD_RPE_STREAK_THRESHOLD = 9.0        # BR-04
DELOAD_STREAK_LENGTH = 3                 # BR-04

BASE_INCREMENT_PCT = 0.025               # §5.3/§5.4 baseline: +2.5%
FAST_TRACK_INCREMENT_PCT = 0.05          # §5.3 modifier: RPE <= 6 at ceiling -> +5%
ADVANCED_DAMPENING = 0.6                 # §8.9: advanced lifters get smaller jumps
                                          # (turns the 2.5%/5% baseline into
                                          # roughly 1.5%/3%, inside the "+1-2.5%"
                                          # advanced band the white paper specifies)

BEGINNER_UPPER_KG_PER_WEEK = 2.5         # §8.2
BEGINNER_LOWER_KG_PER_WEEK = 5.0         # §8.2
LINEAR_FAILURE_STREAK = 2                # §8.2 — 2 misses in a row -> switch strategy

DELOAD_WEIGHT_MULTIPLIER = 0.65          # §8.5 says -30-40%; we use -35% as the midpoint
DELOAD_RPE_TARGET_MIN = 5                # §8.5: "RPE-doel <= 6" — used by all three strategies
DELOAD_RPE_TARGET_MAX = 6


# ---------------------------------------------------------------------------
# Shared math (see NOTE at top of file re: reconciling with formulas.py)
# ---------------------------------------------------------------------------

def brzycki(weight_kg: float, reps: int) -> float | None:
    """
    Estimated 1RM via Brzycki. BR-07: only valid for reps <= 10.
    e1RM = weight * 36 / (37 - reps)
    """
    if reps is None or reps < 1 or reps > 10:
        return None
    if reps == 1:
        return weight_kg
    return weight_kg * 36 / (37 - reps)


def round_to_plate(weight_kg: float, is_barbell: bool = True, fine: bool = False) -> float:
    """
    §5.4 — round to the nearest loadable increment.
    Barbell: nearest 2.5 kg plate jump, or 1.25 kg with `fine=True` for
    lifters using microplates. Dumbbell/machine: nearest 2 kg step.

    The `fine` option exists for §8.9's advanced-lifter dampening: without
    it, a damped ~1.5% increase at typical training weights rounds right
    back up to the same 2.5 kg jump an intermediate lifter would get,
    silently erasing the dampening. Real advanced/competitive lifters
    commonly use 1.25 kg microplates for exactly this reason.
    """
    if is_barbell:
        step = 1.25 if fine else 2.5
    else:
        step = 2.0
    return round(weight_kg / step) * step


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SetLog:
    weight_kg: float
    reps: int
    rpe: float | None = None
    is_warmup: bool = False


@dataclass
class SessionLog:
    performed_at: date
    sets: list[SetLog] = field(default_factory=list)

    def working_sets(self) -> list[SetLog]:
        """BR-08 + §5.9: exclude warmups and sets so extreme they're
        almost certainly a logging error rather than real training data."""
        return [
            s for s in self.sets
            if not s.is_warmup and s.reps <= OUTLIER_MAX_REPS
        ]

    def best_set(self) -> SetLog | None:
        """Highest tonnage single set (weight x reps) — the reference
        point for hypertrophy double progression (§5.3)."""
        ws = self.working_sets()
        return max(ws, key=lambda s: s.weight_kg * s.reps) if ws else None

    def heaviest_valid_set(self) -> SetLog | None:
        """Heaviest set with reps <= 10 (BR-07) — the reference point for
        e1RM / strength autoregulation (§5.4). A session done entirely in
        higher-rep ranges yields no valid e1RM set, which is correct:
        Brzycki simply isn't reliable there."""
        candidates = [s for s in self.working_sets() if s.reps <= 10]
        return max(candidates, key=lambda s: s.weight_kg) if candidates else None

    def avg_rpe(self) -> float | None:
        """Missing RPE values are excluded from the average rather than
        treated as 0 — an unlogged RPE shouldn't silently drag the
        average down (§16 edge case #12)."""
        rpes = [s.rpe for s in self.working_sets() if s.rpe is not None]
        return sum(rpes) / len(rpes) if rpes else None

    def tonnage(self) -> float:
        return sum(s.weight_kg * s.reps for s in self.working_sets())

    def e1rm(self) -> float | None:
        top = self.heaviest_valid_set()
        return brzycki(top.weight_kg, top.reps) if top else None


@dataclass
class Advice:
    weight_kg: float | None
    reps_min: int | None
    reps_max: int | None
    rpe_target_min: float
    rpe_target_max: float
    reason: str                              # BR-01
    provisional: bool = False                # §5.8
    cold_start: bool = False                  # §5.8
    deload: bool = False                      # §8.5 / BR-04
    strategy_switch_recommended: str | None = None   # §8.2 (linear -> double progression)

    def rpe_target_display(self) -> str:
        if self.rpe_target_min == self.rpe_target_max:
            return f"RPE {self.rpe_target_min:g}"
        return f"RPE {self.rpe_target_min:g}-{self.rpe_target_max:g}"


@dataclass
class ExerciseProfile:
    """The subset of `exercises` table metadata (§9) the predictor needs.
    Caller maps this from a SQLAlchemy row — see PREDICTOR_INTEGRATION.md."""
    is_compound: bool
    is_upper_body: bool = True
    is_barbell: bool = True
    linear_target_reps: int = 5  # §8.2 — prescribed reps for beginner linear
                                  # progression (5 is the common default, e.g.
                                  # 5x5-style programs); this is a property of
                                  # the program, not something to infer from
                                  # the session being evaluated.


@dataclass
class UserProfile:
    """The subset of `users` table fields (§9) the predictor needs."""
    global_goal: Literal["hypertrophy", "strength"]
    experience: Literal["beginner", "intermediate", "advanced"] = "intermediate"
    sleep_score: int | None = None            # 1-5, §4.3/§8.8
    stress_score: int | None = None           # 1-5, §4.3/§8.8


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hypertrophy_rep_range(is_compound: bool) -> tuple[int, int]:
    """§5.6: compound 8-12, isolation 12-15."""
    return (8, 12) if is_compound else (12, 15)


def filter_recent_sessions(history: list[SessionLog], as_of: date | None = None) -> list[SessionLog]:
    """§5.9: sessions older than 90 days don't count toward recommendations
    (detraining) — the engine effectively restarts in provisional mode."""
    as_of = as_of or date.today()
    cutoff = as_of - timedelta(days=STALE_SESSION_DAYS)
    return [s for s in history if s.performed_at >= cutoff]


def regression_slope(values: list[float]) -> float | None:
    """
    §5.7 — linear regression of value (e1RM or best-set tonnage) over
    session index. BR-06: fewer than 5 points -> None, meaning "no trend
    available yet"; callers should treat this permissively (rules lead,
    regression supports), not as a blocker.
    """
    if len(values) < REGRESSION_MIN_POINTS:
        return None
    x = np.arange(len(values)).reshape(-1, 1)
    y = np.array(values, dtype=float)
    model = LinearRegression().fit(x, y)
    return float(model.coef_[0])


def regression_predict_next(values: list[float]) -> float | None:
    """§5.7c — one-step-ahead prediction, used for the 'expected' dotted
    line in progression charts (dashboard/analytics, not used internally
    by the recommenders themselves)."""
    if len(values) < REGRESSION_MIN_POINTS:
        return None
    x = np.arange(len(values)).reshape(-1, 1)
    y = np.array(values, dtype=float)
    model = LinearRegression().fit(x, y)
    return float(model.predict(np.array([[len(values)]]))[0])


def regression_slope_over_days(dated_values: list[tuple[int, float]]) -> float | None:
    """
    Like regression_slope, but keyed by day-offset rather than sequential
    session index. §8.6's plateau threshold is stated as "% e1RM per
    week," which only means something if trend is normalized against real
    elapsed time — two lifters logging 6 sessions in 2 weeks vs. 6 weeks
    need different treatment, and session-index regression can't tell
    them apart. Used by engine/warning_detector.py; BR-06's 5-point
    minimum still applies.
    """
    if len(dated_values) < REGRESSION_MIN_POINTS:
        return None
    x = np.array([d for d, _ in dated_values]).reshape(-1, 1)
    y = np.array([v for _, v in dated_values], dtype=float)
    model = LinearRegression().fit(x, y)
    return float(model.coef_[0])  # slope per day


def deload_streak_triggered(sessions: list[SessionLog]) -> bool:
    """
    BR-04: RPE >= 9 in each of the last 3 (or more) consecutive sessions
    triggers a deload. A session with no logged RPE breaks the streak
    rather than extending it — missing data shouldn't silently force a
    deload the lifter never actually earned (or avoided).
    """
    recent = sessions[-DELOAD_STREAK_LENGTH:]
    if len(recent) < DELOAD_STREAK_LENGTH:
        return False
    rpes = [s.avg_rpe() for s in recent]
    if any(r is None for r in rpes):
        return False
    return all(r >= DELOAD_RPE_STREAK_THRESHOLD for r in rpes)


def clamp_weight_change(new_weight: float, last_weight: float) -> float:
    """BR-03: a progression recommendation never moves more than 5% away
    from the last working weight. Deliberately not used for deload advice,
    where a large intentional drop is the entire point."""
    max_up = last_weight * (1 + MAX_WEIGHT_DEVIATION_PCT)
    max_down = last_weight * (1 - MAX_WEIGHT_DEVIATION_PCT)
    return min(max(new_weight, max_down), max_up)


def linear_progression_failing(sessions: list[SessionLog], target_reps: int) -> bool:
    """
    §8.2 — two consecutive sessions landing under the target rep count
    signals that linear progression has run its course for this exercise;
    the dispatcher/caller is responsible for actually switching the
    stored strategy (this function only detects the condition, since the
    switch itself is cross-session state that lives in the database, not
    in these pure functions).
    """
    if len(sessions) < LINEAR_FAILURE_STREAK:
        return False
    recent = sessions[-LINEAR_FAILURE_STREAK:]
    tops = [s.best_set() for s in recent]
    if any(t is None for t in tops):
        return False
    return all(t.reps < target_reps for t in tops)


def apply_recovery_adjustment(
    advice: Advice, last_session: SessionLog | None, profile: UserProfile
) -> Advice:
    """
    §8.8 — self-reported sleep <=2/5 or stress >=4/5 lowers RPE targets by
    1 point for the week and suppresses weight increases (holds at last
    session's reference weight instead). Deloads pass through untouched —
    recovery adjustment shouldn't fight a deload that's already in effect.
    """
    if advice.deload:
        return advice

    poor_sleep = profile.sleep_score is not None and profile.sleep_score <= 2
    high_stress = profile.stress_score is not None and profile.stress_score >= 4
    if not (poor_sleep or high_stress) or last_session is None:
        return advice

    reference = last_session.heaviest_valid_set() or last_session.best_set()
    weight_kg = advice.weight_kg
    if reference is not None and weight_kg is not None and weight_kg > reference.weight_kg:
        weight_kg = reference.weight_kg  # suppress the increase -> hold instead

    advice.weight_kg = weight_kg
    advice.rpe_target_min = max(advice.rpe_target_min - 1, 5)
    advice.rpe_target_max = max(advice.rpe_target_max - 1, 5)
    advice.reason = advice.reason + " Aangepast vanwege je herstel-check-in."
    return advice


def scale_advice_for_experience(
    advice: Advice, last_weight: float | None, exercise: ExerciseProfile, profile: UserProfile
) -> Advice:
    """
    §8.9 — advanced lifters get smaller increments than the baseline
    (intermediate) rules produce (+1-2.5% vs +2.5%/+5%). Only dampens
    genuine increases; holds, consolidations, and deloads pass through
    unchanged, and beginners are unaffected (they use recommend_linear,
    which has its own fixed kg/week increments).
    """
    if profile.experience != "advanced" or advice.deload or advice.weight_kg is None:
        return advice
    if last_weight is None or advice.weight_kg <= last_weight:
        return advice

    delta = advice.weight_kg - last_weight
    scaled = round_to_plate(last_weight + delta * ADVANCED_DAMPENING, exercise.is_barbell, fine=True)
    advice.weight_kg = clamp_weight_change(scaled, last_weight)
    return advice


# ---------------------------------------------------------------------------
# Strategy functions — identical signature: (sessions, profile, exercise) -> Advice
# per the white paper's own architecture note (ch. 8 summary).
# ---------------------------------------------------------------------------

def recommend_hypertrophy(
    sessions: list[SessionLog], profile: UserProfile, exercise: ExerciseProfile
) -> Advice:
    """§5.3 + §8.1 — double progression, the default hypertrophy method."""
    last = sessions[-1]
    top = last.best_set()

    if top is None:
        return Advice(
            weight_kg=None, reps_min=None, reps_max=None,
            rpe_target_min=7, rpe_target_max=8,
            reason="Geen bruikbare sets in de vorige sessie — kies zelf een startgewicht, RPE 7.",
            provisional=True,
        )

    floor, ceiling = hypertrophy_rep_range(exercise.is_compound)
    avg_rpe = last.avg_rpe()
    rpe_str = f"{avg_rpe:.1f}" if avg_rpe is not None else "?"

    # BR-04 overrides double progression entirely, regardless of phase.
    if deload_streak_triggered(sessions):
        return Advice(
            weight_kg=round_to_plate(top.weight_kg * DELOAD_WEIGHT_MULTIPLIER, exercise.is_barbell),
            reps_min=floor, reps_max=floor,
            rpe_target_min=DELOAD_RPE_TARGET_MIN, rpe_target_max=DELOAD_RPE_TARGET_MAX,
            reason="3x RPE >= 9 op rij -> deload-sessie (-35% belasting, -1 set).",
            deload=True,
        )

    if avg_rpe is not None and avg_rpe >= RPE_CONSOLIDATE_THRESHOLD:
        return Advice(
            weight_kg=top.weight_kg, reps_min=top.reps, reps_max=top.reps,
            rpe_target_min=7, rpe_target_max=8,
            reason=f"Laatste sessie RPE {rpe_str} was maximaal -> dezelfde belasting herhalen.",
        )

    if top.reps < ceiling:
        # Phase 1: still room in the rep range.
        target = min(top.reps + 2, ceiling)
        return Advice(
            weight_kg=top.weight_kg,
            reps_min=min(top.reps + 1, target), reps_max=target,
            rpe_target_min=7, rpe_target_max=8,
            reason=f"Laatste: {top.weight_kg:g} kg x {top.reps} @ RPE {rpe_str}. Nog ruimte in de rep-range.",
        )

    # Phase 2: rep ceiling hit -> increase weight, reset reps to floor.
    fast_track = avg_rpe is not None and avg_rpe <= RPE_FAST_TRACK_THRESHOLD
    increment = FAST_TRACK_INCREMENT_PCT if fast_track else BASE_INCREMENT_PCT
    new_weight = clamp_weight_change(
        round_to_plate(top.weight_kg * (1 + increment), exercise.is_barbell), top.weight_kg
    )
    pct_label = f"+{increment * 100:g}%"
    return Advice(
        weight_kg=new_weight, reps_min=floor, reps_max=min(floor + 2, ceiling),
        rpe_target_min=7, rpe_target_max=8,
        reason=f"Bovengrens rep-range gehaald ({ceiling} reps) -> {pct_label} gewicht, reps resetten naar {floor}.",
    )


def recommend_strength(
    sessions: list[SessionLog], profile: UserProfile, exercise: ExerciseProfile
) -> Advice:
    """§5.4 — RPE-autoregulated strength progression, trend-assisted by regression."""
    last = sessions[-1]
    top = last.heaviest_valid_set()

    if top is None:
        return Advice(
            weight_kg=None, reps_min=None, reps_max=None,
            rpe_target_min=8, rpe_target_max=8,
            reason="Geen geldige set (reps <= 10) in de vorige sessie — kies zelf een startgewicht.",
            provisional=True,
        )

    avg_rpe = last.avg_rpe()
    rpe_str = f"{avg_rpe:.1f}" if avg_rpe is not None else "?"
    e1rm_series = [e for e in (s.e1rm() for s in sessions) if e is not None]
    trend = regression_slope(e1rm_series)
    current_e1rm = brzycki(top.weight_kg, top.reps)
    e1rm_str = f"{current_e1rm:.1f} kg" if current_e1rm is not None else "onbekend"

    # BR-04 overrides everything else.
    if deload_streak_triggered(sessions):
        return Advice(
            weight_kg=round_to_plate(top.weight_kg * DELOAD_WEIGHT_MULTIPLIER, exercise.is_barbell),
            reps_min=8, reps_max=8,
            rpe_target_min=DELOAD_RPE_TARGET_MIN, rpe_target_max=DELOAD_RPE_TARGET_MAX,
            reason="3x RPE >= 9-10 op rij -> deload-sessie.",
            deload=True,
        )

    if avg_rpe is not None and avg_rpe <= 8 and (trend is None or trend >= 0):
        new_weight = clamp_weight_change(
            round_to_plate(top.weight_kg * (1 + BASE_INCREMENT_PCT), exercise.is_barbell), top.weight_kg
        )
        return Advice(
            weight_kg=new_weight, reps_min=top.reps, reps_max=top.reps,
            rpe_target_min=8, rpe_target_max=8,
            reason=f"e1RM {e1rm_str}, RPE {rpe_str} <= 8 -> +2,5%.",
        )

    if avg_rpe is not None and avg_rpe >= RPE_HOLD_THRESHOLD:
        return Advice(
            weight_kg=top.weight_kg, reps_min=top.reps, reps_max=top.reps,
            rpe_target_min=8, rpe_target_max=8,
            reason=f"RPE {rpe_str} >= 9 -> gewicht aanhouden, techniek/vermoeidheid herstellen.",
        )

    return Advice(
        weight_kg=top.weight_kg, reps_min=top.reps, reps_max=top.reps,
        rpe_target_min=8, rpe_target_max=8,
        reason="Trend vlak -> consolideren.",
    )


def recommend_linear(
    sessions: list[SessionLog], profile: UserProfile, exercise: ExerciseProfile
) -> Advice:
    """
    §8.2 — beginner linear progression: fixed kg/week increase while
    RPE stays at or below 8. Reps are held at whatever the lifter has
    been doing (the program's fixed rep scheme), since linear programs
    progress on load, not reps.
    """
    last = sessions[-1]
    top = last.best_set()

    if top is None:
        return Advice(
            weight_kg=None, reps_min=None, reps_max=None,
            rpe_target_min=7, rpe_target_max=8,
            reason="Geen bruikbare sets in de vorige sessie — kies zelf een startgewicht.",
            provisional=True,
        )

    avg_rpe = last.avg_rpe()
    rpe_str = f"{avg_rpe:.1f}" if avg_rpe is not None else "?"

    # BR-04 applies here too — beginners aren't exempt from deload logic.
    if deload_streak_triggered(sessions):
        return Advice(
            weight_kg=round_to_plate(top.weight_kg * DELOAD_WEIGHT_MULTIPLIER, exercise.is_barbell),
            reps_min=top.reps, reps_max=top.reps,
            rpe_target_min=DELOAD_RPE_TARGET_MIN, rpe_target_max=DELOAD_RPE_TARGET_MAX,
            reason="3x RPE >= 9 op rij -> deload-sessie.",
            deload=True,
        )

    switch_hint = (
        "double_progression"
        if linear_progression_failing(sessions, exercise.linear_target_reps)
        else None
    )

    if avg_rpe is not None and avg_rpe > 8:
        return Advice(
            weight_kg=top.weight_kg, reps_min=top.reps, reps_max=top.reps,
            rpe_target_min=7, rpe_target_max=8,
            reason=f"RPE {rpe_str} > 8 -> gewicht aanhouden.",
            strategy_switch_recommended=switch_hint,
        )

    increment = BEGINNER_UPPER_KG_PER_WEEK if exercise.is_upper_body else BEGINNER_LOWER_KG_PER_WEEK
    return Advice(
        weight_kg=round(top.weight_kg + increment, 1),
        reps_min=top.reps, reps_max=top.reps,
        rpe_target_min=7, rpe_target_max=8,
        reason=f"Lineaire progressie (beginner) -> +{increment:g} kg.",
        strategy_switch_recommended=switch_hint,
    )


# ---------------------------------------------------------------------------
# Dispatcher — the single entry point api/suggestions.py should call.
# ---------------------------------------------------------------------------

def get_recommendation(
    history: list[SessionLog],
    profile: UserProfile,
    exercise: ExerciseProfile,
    as_of: date | None = None,
) -> Advice:
    """
    §5.2 pipeline: filter -> cold-start check -> dispatch by experience/goal
    -> recovery adjustment. This is what api/suggestions.py's
    GET /api/recommendations?exercise_id= route should call per exercise.

    `history` should be ALL logged sessions for this (user, exercise) pair,
    unfiltered and in any order — this function handles staleness
    filtering (§5.9), sorting, and windowing (last 10, §5.7) internally.
    """
    if profile.global_goal not in ("hypertrophy", "strength"):
        raise ValueError(f"Unknown global_goal: {profile.global_goal!r}")  # BR-02 guard

    as_of = as_of or date.today()
    recent = filter_recent_sessions(history, as_of)
    recent = sorted(recent, key=lambda s: s.performed_at)[-10:]  # §5.7 window
    n = len(recent)

    # §5.8 cold-start ladder: zero history means no weight recommendation at all.
    if n == 0:
        if profile.global_goal == "hypertrophy":
            floor, ceiling = hypertrophy_rep_range(exercise.is_compound)
        else:
            floor, ceiling = 5, 5
        return Advice(
            weight_kg=None, reps_min=floor, reps_max=ceiling,
            rpe_target_min=7, rpe_target_max=7,
            reason="Nog geen historie voor deze oefening — kies zelf een startgewicht, RPE 7.",
            cold_start=True, provisional=True,
        )

    # Route to the right strategy. Experience gates first (§8.9: beginners
    # use linear progression regardless of goal); goal gates second
    # (BR-02: exactly two branches once past the beginner case).
    last_reference = recent[-1].heaviest_valid_set() or recent[-1].best_set()
    last_weight = last_reference.weight_kg if last_reference else None

    if profile.experience == "beginner":
        advice = recommend_linear(recent, profile, exercise)
    elif profile.global_goal == "hypertrophy":
        advice = recommend_hypertrophy(recent, profile, exercise)
    else:
        advice = recommend_strength(recent, profile, exercise)

    if n < COLD_START_MIN_SESSIONS:
        advice.provisional = True  # §5.8: 1-4 sessions -> rule-based, no regression yet

    advice = scale_advice_for_experience(advice, last_weight, exercise, profile)
    advice = apply_recovery_adjustment(advice, recent[-1], profile)
    return advice

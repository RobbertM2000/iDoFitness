"""
engine/wod_generator.py
------------------------
Assembles a full training-day suggestion: which exercises, in what
order, how many sets, how much rest, and (via predictor.py) what weight
and RPE to aim for. White Paper references: §5.5 (exercise selection),
§5.6 (sets/reps/RPE/rest/order/duration), §6.1 (output contract), §5.8
(cold start), BR-05 (never exceed available time).

Division of responsibility with predictor.py: predictor.py already
answers "what weight/reps/RPE for this one exercise" — this module does
NOT reinvent that. It answers the questions predictor.py doesn't:
which exercises to pick, in what order, how many sets, how much rest,
and whether the whole session fits in the time available.

Division of responsibility with the caller (future api/suggestions.py):
this module assumes `candidates` has ALREADY been filtered down to
exercises matching the user's equipment and NOT on their avoid-list
(§5.5 point 3) — that's a straightforward SQL WHERE clause, not
something worth reimplementing in a pure function. This module only
decides, among the candidates it's given, which ones make it into
today's session and in what shape.
"""

from dataclasses import dataclass, field
from datetime import date

from engine.predictor import (
    SessionLog,
    UserProfile,
    ExerciseProfile,
    Advice,
    get_recommendation,
    round_to_plate,
)


# ---------------------------------------------------------------------------
# Constants — White Paper §5.6 table
# ---------------------------------------------------------------------------

HYPERTROPHY_MIN_EXERCISES = 4
HYPERTROPHY_MAX_EXERCISES = 6

STRENGTH_MAIN_LIFTS_MIN = 1
STRENGTH_MAIN_LIFTS_MAX = 2
STRENGTH_ACCESSORIES_MIN = 2
STRENGTH_ACCESSORIES_MAX = 3

HYPERTROPHY_COMPOUND_SETS = 4
HYPERTROPHY_ISOLATION_SETS = 3
HYPERTROPHY_COMPOUND_REST_SEC = 150     # 2-3 min -> midpoint
HYPERTROPHY_ISOLATION_REST_SEC = 75     # 60-90s -> midpoint

STRENGTH_MAIN_LIFT_SETS = 4             # 3-5 -> midpoint
STRENGTH_ACCESSORY_SETS = 3
STRENGTH_MAIN_LIFT_REST_SEC = 240       # 3-5 min -> midpoint
STRENGTH_ACCESSORY_REST_SEC = 120       # 2 min

SET_TIME_SEC = 40                       # §5.6 duration formula
WARMUP_GENERAL_MINUTES = 8              # §5.6: "+ 8 min warming-up"
FREQUENCY_WINDOW_DAYS = 7               # §5.5: "afgelopen 7 dagen (rolling window)"

WARMUP_RAMP = [
    {"pct": 50, "reps": 8},
    {"pct": 70, "reps": 5},
    {"pct": 85, "reps": 2},
]

COOLDOWN_TEXT = "5 min rustig uitlopen/stretchen"
WARMUP_GENERAL_TEXT = "5 min cardio naar keuze"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ExerciseInfo:
    """The subset of `exercises` table metadata (§9) the generator needs.
    Caller maps this from a SQLAlchemy row, already filtered to the
    user's equipment and avoid-list (§5.5 point 3)."""
    exercise_id: int
    name: str
    muscle_group: str
    is_compound: bool
    is_main_lift: bool = False


@dataclass
class WodExercise:
    order: int
    exercise_id: int
    name: str
    sets: int
    reps_min: int | None
    reps_max: int | None
    rpe_target_min: float
    rpe_target_max: float
    rest_sec: int
    weight_kg: float | None
    reason: str
    provisional: bool
    cold_start: bool
    is_compound: bool


@dataclass
class WarmupPlan:
    general: str
    ramp_sets: list[dict] = field(default_factory=list)
    note: str | None = None    # populated when there's no known working
                                # weight to ramp toward (§5.8 cold start)


@dataclass
class WodPlan:
    date: date
    goal: str
    title: str
    estimated_duration_min: int
    warmup: WarmupPlan
    exercises: list[WodExercise]
    cooldown: str
    cold_start: bool            # true only when EVERY exercise is cold-start
                                 # (i.e. a genuinely new user, §5.8's
                                 # "nieuwe gebruiker" case) — not just one
                                 # never-logged exercise among familiar ones


# ---------------------------------------------------------------------------
# Frequency analysis — §5.5 point 1
# ---------------------------------------------------------------------------

def _distinct_training_days(sessions: list[SessionLog], as_of: date, window_days: int) -> int:
    return len({
        s.performed_at for s in sessions
        if 0 <= (as_of - s.performed_at).days < window_days
    })


def _muscle_group_frequency(
    candidates: list[ExerciseInfo],
    histories: dict[int, list[SessionLog]],
    as_of: date,
) -> dict[str, int]:
    """Distinct training days per muscle group in the trailing 7 days,
    unioned across every candidate exercise that touches that group."""
    by_group: dict[str, set] = {}
    for ex in candidates:
        sessions = histories.get(ex.exercise_id, [])
        for s in sessions:
            if 0 <= (as_of - s.performed_at).days < FREQUENCY_WINDOW_DAYS:
                by_group.setdefault(ex.muscle_group, set()).add(s.performed_at)
    all_groups = {ex.muscle_group for ex in candidates}
    return {g: len(by_group.get(g, set())) for g in all_groups}


def _last_trained(exercise_id: int, histories: dict[int, list[SessionLog]]) -> date:
    sessions = histories.get(exercise_id, [])
    return max((s.performed_at for s in sessions), default=date.min)


# ---------------------------------------------------------------------------
# Candidate ranking — §5.5 points 2-4
# ---------------------------------------------------------------------------

def _rank_within_groups(
    exercises: list[ExerciseInfo],
    groups_by_priority: list[str],
    histories: dict[int, list[SessionLog]],
) -> list[ExerciseInfo]:
    """§5.5 point 4: compound before isolation, most-recent-history first,
    within each muscle group — then interleaved across groups in priority
    order (one pick per group per pass) so a session needing more than
    one exercise per group still respects overall muscle-group priority."""
    by_group: dict[str, list[ExerciseInfo]] = {}
    for ex in exercises:
        by_group.setdefault(ex.muscle_group, []).append(ex)

    for g in by_group:
        by_group[g].sort(
            key=lambda ex: (not ex.is_compound, -_last_trained(ex.exercise_id, histories).toordinal())
        )

    ranked: list[ExerciseInfo] = []
    used = {g: 0 for g in by_group}
    progress = True
    while progress:
        progress = False
        for g in groups_by_priority:
            idx = used.get(g, 0)
            group_list = by_group.get(g, [])
            if idx < len(group_list):
                ranked.append(group_list[idx])
                used[g] = idx + 1
                progress = True
    return ranked


def _select_hypertrophy_candidates(
    candidates: list[ExerciseInfo],
    histories: dict[int, list[SessionLog]],
    as_of: date,
) -> list[ExerciseInfo]:
    """§5.5 points 1-2: muscle groups trained fewer days this week come
    first (frequency target is 2-3x/week, so <2 needs priority)."""
    freq = _muscle_group_frequency(candidates, histories, as_of)
    groups_by_priority = sorted(freq.keys(), key=lambda g: (freq[g], g))
    return _rank_within_groups(candidates, groups_by_priority, histories)


def _select_strength_candidates(
    candidates: list[ExerciseInfo],
    histories: dict[int, list[SessionLog]],
    as_of: date,
) -> tuple[list[ExerciseInfo], list[ExerciseInfo]]:
    """§5.5 point 2 (strength branch): the main lift not yet done this
    week comes first. Returns (ranked_main_lifts, ranked_accessories)
    separately, since they fill different slot budgets (§5.6)."""
    main_lifts = [ex for ex in candidates if ex.is_main_lift]
    accessories = [ex for ex in candidates if not ex.is_main_lift]

    def main_lift_sort_key(ex: ExerciseInfo):
        last = _last_trained(ex.exercise_id, histories)
        done_this_week = _distinct_training_days(
            histories.get(ex.exercise_id, []), as_of, FREQUENCY_WINDOW_DAYS
        ) > 0
        has_history = last != date.min
        # not-done-this-week first; among ties, a lift the user has SOME
        # track record with (however old) is more "overdue" than one
        # they've never attempted, so it's prioritized ahead of it
        return (done_this_week, not has_history, last)

    main_lifts.sort(key=main_lift_sort_key)

    freq = _muscle_group_frequency(accessories, histories, as_of)
    groups_by_priority = sorted(freq.keys(), key=lambda g: (freq[g], g))
    ranked_accessories = _rank_within_groups(accessories, groups_by_priority, histories)

    return main_lifts, ranked_accessories


# ---------------------------------------------------------------------------
# Prescription + duration — §5.6
# ---------------------------------------------------------------------------

def _prescription(exercise: ExerciseInfo, goal: str, is_main_lift_slot: bool) -> tuple[int, int]:
    """Returns (sets, rest_sec). Reps/RPE/weight come from
    get_recommendation() instead — kept as a single source of truth
    rather than a second, possibly-inconsistent rep-range table."""
    if goal == "hypertrophy":
        if exercise.is_compound:
            return HYPERTROPHY_COMPOUND_SETS, HYPERTROPHY_COMPOUND_REST_SEC
        return HYPERTROPHY_ISOLATION_SETS, HYPERTROPHY_ISOLATION_REST_SEC
    if is_main_lift_slot:
        return STRENGTH_MAIN_LIFT_SETS, STRENGTH_MAIN_LIFT_REST_SEC
    return STRENGTH_ACCESSORY_SETS, STRENGTH_ACCESSORY_REST_SEC


def _duration_min(prescribed: list[tuple[ExerciseInfo, int, int]]) -> int:
    """§5.6: Σ per oefening (sets x (settijd 40s + rust)) + 8 min warming-up."""
    total_sec = sum(sets * (SET_TIME_SEC + rest_sec) for _, sets, rest_sec in prescribed)
    return round(total_sec / 60) + WARMUP_GENERAL_MINUTES


def _target_exercise_count(session_minutes: int, low: int, high: int) -> int:
    """Scales the White Paper's exercise-count range to session length:
    <=30 min sessions get the low end, >=90 min get the high end."""
    if session_minutes <= 30:
        return low
    if session_minutes >= 90:
        return high
    frac = (session_minutes - 30) / (90 - 30)
    return round(low + frac * (high - low))


def _fill_to_duration(
    ranked_candidates: list[ExerciseInfo],
    goal: str,
    session_minutes: int,
    target_count: int,
    main_lift_ids: set[int] | None = None,
) -> list[tuple[ExerciseInfo, int, int]]:
    """BR-05: adds exercises one at a time, in priority order, stopping
    the instant the projected session would exceed the user's available
    time — but always keeps at least one exercise, even if it alone runs
    long, so the session is never empty."""
    main_lift_ids = main_lift_ids or set()
    selected: list[tuple[ExerciseInfo, int, int]] = []
    for ex in ranked_candidates:
        if len(selected) >= target_count:
            break
        is_main_slot = ex.exercise_id in main_lift_ids
        sets, rest_sec = _prescription(ex, goal, is_main_slot)
        trial = selected + [(ex, sets, rest_sec)]
        if _duration_min(trial) > session_minutes and selected:
            break
        selected.append((ex, sets, rest_sec))
    return selected


def _final_order(prescribed: list[tuple[ExerciseInfo, int, int]], main_lift_ids: set[int]) -> list[tuple]:
    """§5.6: main lift(s) first (strength), then compound before
    isolation, grote voor kleine spiergroep — approximated here as a
    stable sort that preserves each item's selection-priority position
    within its (main-lift, compound) bucket."""
    return sorted(
        enumerate(prescribed),
        key=lambda pair: (
            0 if pair[1][0].exercise_id in main_lift_ids else 1,
            not pair[1][0].is_compound,
            pair[0],   # stable: preserve original priority order within buckets
        ),
    )


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------

def _build_warmup(exercises: list[WodExercise]) -> WarmupPlan:
    first_compound_with_weight = next(
        (e for e in exercises if e.is_compound and e.weight_kg is not None), None
    )
    if first_compound_with_weight is None:
        return WarmupPlan(
            general=WARMUP_GENERAL_TEXT,
            ramp_sets=[],
            note="Nog geen werkgewicht bekend — kies zelf een opwarmgewicht, RPE 7.",
        )
    w = first_compound_with_weight.weight_kg
    ramp_sets = [
        {"pct": step["pct"], "reps": step["reps"], "weight_kg": round_to_plate(w * step["pct"] / 100)}
        for step in WARMUP_RAMP
    ]
    return WarmupPlan(general=WARMUP_GENERAL_TEXT, ramp_sets=ramp_sets)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_wod(
    candidates: list[ExerciseInfo],
    histories: dict[int, list[SessionLog]],
    profile: UserProfile,
    session_minutes: int,
    as_of: date | None = None,
) -> WodPlan:
    """
    §5.2/§5.5/§5.6 pipeline. `candidates` must already be filtered to the
    user's equipment and avoid-list (§5.5 point 3) — see this module's
    docstring. `histories` maps exercise_id -> that exercise's full
    SessionLog history (same shape predictor.py expects).
    """
    if profile.global_goal not in ("hypertrophy", "strength"):
        raise ValueError(f"Unknown global_goal: {profile.global_goal!r}")  # BR-02

    as_of = as_of or date.today()

    if not candidates:
        return WodPlan(
            date=as_of, goal=profile.global_goal, title="Geen oefeningen beschikbaar",
            estimated_duration_min=0, warmup=WarmupPlan(general=WARMUP_GENERAL_TEXT),
            exercises=[], cooldown=COOLDOWN_TEXT, cold_start=True,
        )

    main_lift_ids: set[int] = set()

    if profile.global_goal == "hypertrophy":
        ranked = _select_hypertrophy_candidates(candidates, histories, as_of)
        target = _target_exercise_count(session_minutes, HYPERTROPHY_MIN_EXERCISES, HYPERTROPHY_MAX_EXERCISES)
        prescribed = _fill_to_duration(ranked, "hypertrophy", session_minutes, target)
        title = "Hypertrofie sessie"
    else:
        main_lifts, accessories = _select_strength_candidates(candidates, histories, as_of)
        main_target = _target_exercise_count(session_minutes, STRENGTH_MAIN_LIFTS_MIN, STRENGTH_MAIN_LIFTS_MAX)
        acc_target = _target_exercise_count(session_minutes, STRENGTH_ACCESSORIES_MIN, STRENGTH_ACCESSORIES_MAX)
        main_lift_ids = {ex.exercise_id for ex in main_lifts[:main_target]}

        prescribed_main = _fill_to_duration(main_lifts, "strength", session_minutes, main_target, main_lift_ids)
        remaining_minutes = session_minutes - _duration_min(prescribed_main) if prescribed_main else session_minutes
        prescribed_acc = _fill_to_duration(accessories, "strength", remaining_minutes, acc_target, main_lift_ids)
        prescribed = prescribed_main + prescribed_acc
        title = "Kracht sessie"

    ordered = _final_order(prescribed, main_lift_ids)

    wod_exercises: list[WodExercise] = []
    for order, (_, (ex, sets, rest_sec)) in enumerate(ordered, start=1):
        exercise_profile = ExerciseProfile(is_compound=ex.is_compound)
        advice: Advice = get_recommendation(
            histories.get(ex.exercise_id, []), profile, exercise_profile, as_of=as_of
        )
        wod_exercises.append(WodExercise(
            order=order,
            exercise_id=ex.exercise_id,
            name=ex.name,
            sets=sets,
            reps_min=advice.reps_min,
            reps_max=advice.reps_max,
            rpe_target_min=advice.rpe_target_min,
            rpe_target_max=advice.rpe_target_max,
            rest_sec=rest_sec,
            weight_kg=advice.weight_kg,
            reason=advice.reason,
            provisional=advice.provisional,
            cold_start=advice.cold_start,
            is_compound=ex.is_compound,
        ))

    duration = round(
        sum(we.sets * (SET_TIME_SEC + we.rest_sec) for we in wod_exercises) / 60
    ) + WARMUP_GENERAL_MINUTES

    return WodPlan(
        date=as_of,
        goal=profile.global_goal,
        title=title,
        estimated_duration_min=duration,
        warmup=_build_warmup(wod_exercises),
        exercises=wod_exercises,
        cooldown=COOLDOWN_TEXT,
        cold_start=all(e.cold_start for e in wod_exercises) if wod_exercises else True,
    )

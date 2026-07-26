"""
engine/demo_wod_generator.py
------------------------------
Runnable demo: generates a full training day for both a hypertrophy
user and a strength user, from the same exercise library and a
realistic mixed training history.

Run from backend/:  py -m engine.demo_wod_generator
"""

from datetime import date, timedelta

from engine.predictor import SetLog, SessionLog, UserProfile
from engine.wod_generator import ExerciseInfo, generate_wod


def build_library():
    return [
        ExerciseInfo(1, "Bench Press", "chest", is_compound=True, is_main_lift=True),
        ExerciseInfo(2, "Incline DB Press", "chest", is_compound=False),
        ExerciseInfo(3, "Cable Fly", "chest", is_compound=False),
        ExerciseInfo(4, "Barbell Row", "back", is_compound=True, is_main_lift=True),
        ExerciseInfo(5, "Lat Pulldown", "back", is_compound=False),
        ExerciseInfo(6, "Squat", "quads", is_compound=True, is_main_lift=True),
        ExerciseInfo(7, "Leg Extension", "quads", is_compound=False),
        ExerciseInfo(8, "Deadlift", "back", is_compound=True, is_main_lift=True),
        ExerciseInfo(9, "Triceps Pushdown", "triceps", is_compound=False),
        ExerciseInfo(10, "Overhead Press", "shoulders", is_compound=True, is_main_lift=True),
    ]


def build_histories(start: date):
    """A believable few weeks: bench and squat trained recently, back
    and shoulders neglected -- exactly the pattern both goal branches
    should notice and correct for."""
    return {
        1: [SessionLog(start - timedelta(days=d), [SetLog(100, 8, 7.0)]) for d in (2, 9, 16)],
        6: [SessionLog(start - timedelta(days=d), [SetLog(140, 5, 8.0)]) for d in (3, 10, 17)],
        4: [SessionLog(start - timedelta(days=20), [SetLog(90, 8, 7.0)])],   # stale
        # back/shoulders/deadlift/triceps: no recent history -> should surface
    }


def print_wod(wod, label):
    print(f"=== {label}: {wod.title} ===")
    print(f"Duration: ~{wod.estimated_duration_min} min | cold_start={wod.cold_start}")
    print(f"Warmup: {wod.warmup.general}", end="")
    if wod.warmup.ramp_sets:
        ramp = ", ".join(f"{r['pct']}%x{r['reps']} ({r['weight_kg']}kg)" for r in wod.warmup.ramp_sets)
        print(f" + {ramp}")
    else:
        print(f" ({wod.warmup.note})")
    for e in wod.exercises:
        weight = f"{e.weight_kg}kg" if e.weight_kg is not None else "kies zelf"
        print(f"  {e.order}. {e.name}: {e.sets}x{e.reps_min}-{e.reps_max} @ RPE "
              f"{e.rpe_target_min}-{e.rpe_target_max}, {weight}, rust {e.rest_sec}s")
        print(f"     reason: {e.reason}")
    print(f"Cooldown: {wod.cooldown}")
    print()


def run():
    start = date(2026, 7, 20)
    candidates = build_library()
    histories = build_histories(start)

    hypertrophy_profile = UserProfile(global_goal="hypertrophy", experience="intermediate")
    strength_profile = UserProfile(global_goal="strength", experience="intermediate")

    hyp_wod = generate_wod(candidates, histories, hypertrophy_profile, session_minutes=60, as_of=start)
    str_wod = generate_wod(candidates, histories, strength_profile, session_minutes=75, as_of=start)

    print_wod(hyp_wod, "Hypertrophy user, 60 min available")
    print_wod(str_wod, "Strength user, 75 min available")


if __name__ == "__main__":
    run()

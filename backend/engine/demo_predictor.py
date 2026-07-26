"""
engine/demo_predictor.py
-------------------------
Runnable demo: an 8-week bench press story showing exactly what the
engine recommends after each logged session, and why (BR-01).

Not a test — a narrative walkthrough. Useful for sanity-checking the
engine by eye, and for the CS50 demo video: it's a clean way to show
the "coaching-quality decisions, no black box" USP (white paper §1.5,
§2.5) in under a minute.

Run from backend/:  py -m engine.demo_predictor
"""

from datetime import date, timedelta

from engine.predictor import (
    SetLog,
    SessionLog,
    ExerciseProfile,
    UserProfile,
    get_recommendation,
)


def run():
    exercise = ExerciseProfile(is_compound=True, is_upper_body=True, is_barbell=True)
    profile = UserProfile(global_goal="hypertrophy", experience="intermediate")

    # weight, reps, RPE per week — a realistic arc: rep progression,
    # a weight bump, then rising fatigue that eventually forces a deload.
    story = [
        (100, 8, 7.0),
        (100, 10, 7.5),
        (100, 12, 8.0),    # ceiling hit -> expect a weight bump next
        (102.5, 8, 7.5),
        (102.5, 10, 8.0),
        (102.5, 10, 9.0),  # fatigue creeping in
        (102.5, 10, 9.5),  # 2nd high-RPE session in a row
        (102.5, 10, 9.5),  # 3rd -> expect BR-04 to force a deload
    ]

    sessions: list[SessionLog] = []
    start = date(2026, 5, 4)

    print("iDoFitness — Recommendation Engine Demo")
    print("Exercise: Bench Press · Goal: Hypertrophy · Experience: Intermediate\n")

    for i, (weight, reps, rpe) in enumerate(story):
        sessions.append(SessionLog(start + timedelta(weeks=i), [SetLog(weight, reps, rpe)]))
        advice = get_recommendation(sessions, profile, exercise, as_of=start + timedelta(weeks=i, days=1))

        flags = []
        if advice.provisional:
            flags.append("PROVISIONAL")
        if advice.deload:
            flags.append("DELOAD")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""

        print(f"Week {i + 1}  logged: {weight}kg x {reps} @ RPE {rpe}")
        print(f"  -> next session: {advice.weight_kg}kg, {advice.reps_min}-{advice.reps_max} reps, "
              f"{advice.rpe_target_display()}{flag_str}")
        print(f"  -> why: {advice.reason}")
        print()


if __name__ == "__main__":
    run()

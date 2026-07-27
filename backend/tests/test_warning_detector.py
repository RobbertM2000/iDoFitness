"""
tests/test_warning_detector.py
--------------------------------
Coverage for engine/warning_detector.py. Synthetic histories only — no
database, no Flask app — matching the "pure functions" design of
predictor.py that this module follows.
"""

from datetime import date, timedelta

from engine.predictor import SetLog, SessionLog
from engine.warning_detector import (
    detect_deload_needed,
    detect_suspicious_jump,
    detect_plateau,
    detect_muscle_imbalance,
    detect_goal_mismatch,
    detect_stale_exercise,
    detect_inactivity,
    detect_warnings,
)

BASE_DATE = date(2026, 7, 20)


def session(days_offset: int, weight: float, reps: int, rpe: float | None):
    return SessionLog(BASE_DATE - timedelta(days=days_offset), [SetLog(weight, reps, rpe)])


# ---------------------------------------------------------------------------
# detect_deload_needed
# ---------------------------------------------------------------------------

def test_deload_needed_triggers_on_three_high_rpe_sessions():
    histories = {
        1: ("Bench Press", [session(21, 100, 5, 9.5), session(14, 100, 5, 9), session(7, 100, 5, 9.5)]),
    }
    result = detect_deload_needed(histories)
    assert result is not None
    assert result.warning_type == "deload_needed"
    assert "Bench Press" in result.message
    assert result.severity == "high"


def test_deload_needed_none_when_rpe_moderate():
    histories = {1: ("Bench Press", [session(14, 100, 5, 7), session(7, 100, 5, 7.5)])}
    assert detect_deload_needed(histories) is None


# ---------------------------------------------------------------------------
# detect_suspicious_jump
# ---------------------------------------------------------------------------

def test_suspicious_jump_detected():
    histories = {1: ("Deadlift", [session(7, 100, 5, 8), session(0, 140, 5, 8)])}
    result = detect_suspicious_jump(histories)
    assert result is not None
    assert result.warning_type == "suspicious_jump"
    assert "Deadlift" in result.message


def test_suspicious_jump_not_triggered_for_normal_progression():
    histories = {1: ("Deadlift", [session(7, 100, 5, 8), session(0, 102.5, 5, 8)])}
    assert detect_suspicious_jump(histories) is None


def test_suspicious_jump_requires_two_sessions():
    histories = {1: ("Deadlift", [session(0, 140, 5, 8)])}
    assert detect_suspicious_jump(histories) is None


# ---------------------------------------------------------------------------
# detect_plateau
# ---------------------------------------------------------------------------

def test_plateau_detected_on_flat_e1rm_trend():
    sessions = [session(28 - i * 7, 100, 5, 8) for i in range(5)]  # identical every session
    histories = {1: ("Back Squat", sessions)}
    result = detect_plateau(histories, BASE_DATE)
    assert result is not None
    assert result.warning_type == "plateau"


def test_plateau_none_when_progressing():
    sessions = [session(28 - i * 7, 90 + i * 5, 5, 8) for i in range(5)]  # +5kg each session
    histories = {1: ("Back Squat", sessions)}
    assert detect_plateau(histories, BASE_DATE) is None


def test_plateau_none_below_minimum_sessions():
    sessions = [session(14, 100, 5, 8), session(7, 100, 5, 8)]
    histories = {1: ("Back Squat", sessions)}
    assert detect_plateau(histories, BASE_DATE) is None


# ---------------------------------------------------------------------------
# detect_muscle_imbalance
# ---------------------------------------------------------------------------

def test_muscle_imbalance_detected():
    result = detect_muscle_imbalance({"chest": 20, "back": 2, "quads": 18})
    assert result is not None
    assert result.warning_type == "muscle_imbalance"
    assert "Chest" in result.message


def test_muscle_imbalance_none_when_balanced():
    result = detect_muscle_imbalance({"chest": 10, "back": 9, "quads": 11})
    assert result is None


def test_muscle_imbalance_none_with_single_group():
    assert detect_muscle_imbalance({"chest": 20}) is None


def test_muscle_imbalance_ignores_low_volume_noise():
    # busiest group under the minimum-sets floor — too little data to call it
    assert detect_muscle_imbalance({"chest": 3, "back": 0}) is None


# ---------------------------------------------------------------------------
# detect_goal_mismatch
# ---------------------------------------------------------------------------

def test_goal_mismatch_strength_user_doing_high_reps():
    reps = [15] * 8 + [5] * 2  # 80% above 8 reps
    result = detect_goal_mismatch("strength", reps)
    assert result is not None
    assert result.warning_type == "goal_mismatch"


def test_goal_mismatch_none_when_aligned():
    reps = [5] * 8 + [15] * 2
    assert detect_goal_mismatch("strength", reps) is None


def test_goal_mismatch_none_below_minimum_sets():
    assert detect_goal_mismatch("strength", [15] * 5) is None


def test_goal_mismatch_hypertrophy_user_doing_very_high_reps():
    reps = [25] * 8 + [10] * 2
    result = detect_goal_mismatch("hypertrophy", reps)
    assert result is not None


# ---------------------------------------------------------------------------
# detect_stale_exercise
# ---------------------------------------------------------------------------

def test_stale_exercise_detected_after_90_days():
    sessions = [session(120, 100, 5, 8), session(110, 100, 5, 8), session(100, 100, 5, 8)]
    histories = {1: ("Overhead Press", sessions)}
    result = detect_stale_exercise(histories, BASE_DATE)
    assert result is not None
    assert result.warning_type == "stale_exercise"


def test_stale_exercise_none_when_recent():
    sessions = [session(21, 100, 5, 8), session(14, 100, 5, 8), session(7, 100, 5, 8)]
    histories = {1: ("Overhead Press", sessions)}
    assert detect_stale_exercise(histories, BASE_DATE) is None


def test_stale_exercise_none_with_too_little_history():
    sessions = [session(120, 100, 5, 8)]
    histories = {1: ("Overhead Press", sessions)}
    assert detect_stale_exercise(histories, BASE_DATE) is None


# ---------------------------------------------------------------------------
# detect_inactivity
# ---------------------------------------------------------------------------

def test_inactivity_none_workout_ever():
    result = detect_inactivity(None, BASE_DATE, 4)
    assert result is not None
    assert result.warning_type == "inactivity"


def test_inactivity_detected_beyond_cadence():
    last = BASE_DATE - timedelta(days=10)
    result = detect_inactivity(last, BASE_DATE, 4)  # expects ~2 days apart
    assert result is not None


def test_inactivity_none_within_cadence():
    last = BASE_DATE - timedelta(days=1)
    assert detect_inactivity(last, BASE_DATE, 4) is None


# ---------------------------------------------------------------------------
# detect_warnings (orchestrator)
# ---------------------------------------------------------------------------

def test_detect_warnings_sorts_by_priority():
    histories = {
        1: ("Bench Press", [session(21, 100, 5, 9.5), session(14, 100, 5, 9), session(7, 100, 5, 9.5)]),
    }
    result = detect_warnings(
        goal="hypertrophy",
        exercise_histories=histories,
        muscle_group_sets={"chest": 20, "back": 1},
        rep_counts=[8] * 10,
        last_workout_date=BASE_DATE - timedelta(days=1),
        days_per_week=4,
        as_of=BASE_DATE,
    )
    # deload_needed (priority 1) must lead muscle_imbalance (priority 4)
    types = [c.warning_type for c in result]
    assert types.index("deload_needed") < types.index("muscle_imbalance")


def test_detect_warnings_empty_for_healthy_user():
    histories = {1: ("Bench Press", [session(7, 100, 5, 7), session(0, 102.5, 5, 7)])}
    result = detect_warnings(
        goal="hypertrophy",
        exercise_histories=histories,
        muscle_group_sets={"chest": 10, "back": 9},
        rep_counts=[10] * 10,
        last_workout_date=BASE_DATE,
        days_per_week=4,
        as_of=BASE_DATE,
    )
    assert result == []

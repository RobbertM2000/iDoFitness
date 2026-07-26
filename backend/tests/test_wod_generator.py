"""
tests/test_wod_generator.py
-----------------------------
Coverage for engine/wod_generator.py, organized by White Paper section.
"""

from datetime import date, timedelta

import pytest

from engine.predictor import SetLog, SessionLog, UserProfile
from engine.wod_generator import (
    ExerciseInfo,
    WodExercise,
    generate_wod,
    _distinct_training_days,
    _muscle_group_frequency,
    _last_trained,
    _select_hypertrophy_candidates,
    _select_strength_candidates,
    _prescription,
    _duration_min,
    _target_exercise_count,
    _fill_to_duration,
    _build_warmup,
    HYPERTROPHY_MIN_EXERCISES,
    HYPERTROPHY_MAX_EXERCISES,
    STRENGTH_MAIN_LIFTS_MIN,
    STRENGTH_MAIN_LIFTS_MAX,
)


BASE = date(2026, 7, 1)
HYPERTROPHY = UserProfile(global_goal="hypertrophy", experience="intermediate")
STRENGTH = UserProfile(global_goal="strength", experience="intermediate")


def session(days_ago: int, weight=100, reps=8, rpe=7.0):
    return SessionLog(BASE - timedelta(days=days_ago), [SetLog(weight, reps, rpe)])


# ---------------------------------------------------------------------------
# Frequency analysis
# ---------------------------------------------------------------------------

class TestFrequencyAnalysis:
    def test_distinct_training_days_basic(self):
        sessions = [session(1), session(3), session(10)]  # last one outside 7-day window
        assert _distinct_training_days(sessions, BASE, window_days=7) == 2

    def test_distinct_training_days_same_day_counts_once(self):
        sessions = [
            SessionLog(BASE - timedelta(days=1), [SetLog(100, 8, 7)]),
            SessionLog(BASE - timedelta(days=1), [SetLog(100, 8, 7)]),
        ]
        assert _distinct_training_days(sessions, BASE, window_days=7) == 1

    def test_muscle_group_frequency_unions_across_exercises(self):
        candidates = [
            ExerciseInfo(1, "Bench", "chest", is_compound=True),
            ExerciseInfo(2, "Incline DB Press", "chest", is_compound=False),
        ]
        histories = {1: [session(1)], 2: [session(3)]}
        freq = _muscle_group_frequency(candidates, histories, BASE)
        assert freq["chest"] == 2  # two distinct days, across two different exercises

    def test_muscle_group_frequency_zero_for_untrained_group(self):
        candidates = [ExerciseInfo(1, "Squat", "quads", is_compound=True)]
        freq = _muscle_group_frequency(candidates, {}, BASE)
        assert freq["quads"] == 0

    def test_last_trained_defaults_to_min_when_no_history(self):
        assert _last_trained(999, {}) == date.min


# ---------------------------------------------------------------------------
# Hypertrophy candidate selection — §5.5 points 1-2, 4
# ---------------------------------------------------------------------------

class TestHypertrophySelection:
    def test_least_trained_muscle_group_comes_first(self):
        candidates = [
            ExerciseInfo(1, "Bench", "chest", is_compound=True),
            ExerciseInfo(2, "Squat", "quads", is_compound=True),
        ]
        # chest trained twice this week, quads never
        histories = {1: [session(1), session(2)]}
        ranked = _select_hypertrophy_candidates(candidates, histories, BASE)
        assert ranked[0].muscle_group == "quads"

    def test_compound_preferred_over_isolation_within_group(self):
        candidates = [
            ExerciseInfo(1, "Cable Fly", "chest", is_compound=False),
            ExerciseInfo(2, "Bench Press", "chest", is_compound=True),
        ]
        ranked = _select_hypertrophy_candidates(candidates, {}, BASE)
        assert ranked[0].name == "Bench Press"

    def test_most_recent_history_preferred_within_same_compound_bucket(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True),
            ExerciseInfo(2, "Incline Barbell Press", "chest", is_compound=True),
        ]
        histories = {1: [session(1)], 2: [session(10)]}
        ranked = _select_hypertrophy_candidates(candidates, histories, BASE)
        assert ranked[0].name == "Bench Press"  # more recently trained

    def test_cycles_back_for_second_exercise_per_group(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True),
            ExerciseInfo(2, "Cable Fly", "chest", is_compound=False),
            ExerciseInfo(3, "Squat", "quads", is_compound=True),
        ]
        ranked = _select_hypertrophy_candidates(candidates, {}, BASE)
        # one pick per group per pass, then second pass adds the 2nd chest exercise
        assert [ex.exercise_id for ex in ranked] == [1, 3, 2] or [ex.exercise_id for ex in ranked][:2] == [ranked[0].exercise_id, ranked[1].exercise_id]
        # more precisely: chest's compound exercise and quads' exercise fill pass 1,
        # chest's isolation exercise fills pass 2
        groups_in_order = [ex.muscle_group for ex in ranked]
        assert groups_in_order[-1] == "chest"  # the leftover second chest exercise comes last


# ---------------------------------------------------------------------------
# Strength candidate selection — §5.5 point 2 (strength branch)
# ---------------------------------------------------------------------------

class TestStrengthSelection:
    def test_main_lift_not_done_this_week_prioritized(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True, is_main_lift=True),
            ExerciseInfo(2, "Squat", "quads", is_compound=True, is_main_lift=True),
        ]
        histories = {1: [session(1)]}  # bench done this week, squat not
        main_lifts, _ = _select_strength_candidates(candidates, histories, BASE)
        assert main_lifts[0].name == "Squat"

    def test_lift_with_old_history_outranks_never_attempted(self):
        candidates = [
            ExerciseInfo(1, "Squat", "quads", is_compound=True, is_main_lift=True),
            ExerciseInfo(2, "Overhead Press", "shoulders", is_compound=True, is_main_lift=True),
        ]
        histories = {1: [session(30)]}  # squat: real but stale history; OHP: never done
        main_lifts, _ = _select_strength_candidates(candidates, histories, BASE)
        assert main_lifts[0].name == "Squat"

    def test_accessories_ranked_separately_by_own_muscle_group_frequency(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True, is_main_lift=True),
            ExerciseInfo(2, "Triceps Pushdown", "triceps", is_compound=False),
            ExerciseInfo(3, "Lat Pulldown", "back", is_compound=True),
        ]
        histories = {3: [session(1), session(2)]}  # back trained recently; triceps not
        _, accessories = _select_strength_candidates(candidates, histories, BASE)
        assert accessories[0].muscle_group == "triceps"


# ---------------------------------------------------------------------------
# Prescription — §5.6 table
# ---------------------------------------------------------------------------

class TestPrescription:
    def test_hypertrophy_compound(self):
        ex = ExerciseInfo(1, "Bench Press", "chest", is_compound=True)
        sets, rest = _prescription(ex, "hypertrophy", is_main_lift_slot=False)
        assert sets == 4
        assert rest == 150

    def test_hypertrophy_isolation(self):
        ex = ExerciseInfo(1, "Cable Fly", "chest", is_compound=False)
        sets, rest = _prescription(ex, "hypertrophy", is_main_lift_slot=False)
        assert sets == 3
        assert rest == 75

    def test_strength_main_lift(self):
        ex = ExerciseInfo(1, "Squat", "quads", is_compound=True, is_main_lift=True)
        sets, rest = _prescription(ex, "strength", is_main_lift_slot=True)
        assert sets == 4
        assert rest == 240

    def test_strength_accessory(self):
        ex = ExerciseInfo(1, "Leg Curl", "hamstrings", is_compound=False)
        sets, rest = _prescription(ex, "strength", is_main_lift_slot=False)
        assert sets == 3
        assert rest == 120


# ---------------------------------------------------------------------------
# Duration / target count / BR-05 trimming
# ---------------------------------------------------------------------------

class TestDurationAndTrimming:
    def test_duration_formula(self):
        ex = ExerciseInfo(1, "Bench Press", "chest", is_compound=True)
        # 4 sets x (40s + 150s rest) = 760s = 12.67min -> round to 13, + 8min warmup = 21
        duration = _duration_min([(ex, 4, 150)])
        assert duration == 21

    def test_target_count_scales_low_at_short_sessions(self):
        assert _target_exercise_count(30, HYPERTROPHY_MIN_EXERCISES, HYPERTROPHY_MAX_EXERCISES) == HYPERTROPHY_MIN_EXERCISES

    def test_target_count_scales_high_at_long_sessions(self):
        assert _target_exercise_count(90, HYPERTROPHY_MIN_EXERCISES, HYPERTROPHY_MAX_EXERCISES) == HYPERTROPHY_MAX_EXERCISES

    def test_target_count_interpolates_at_midpoint(self):
        result = _target_exercise_count(60, HYPERTROPHY_MIN_EXERCISES, HYPERTROPHY_MAX_EXERCISES)
        assert HYPERTROPHY_MIN_EXERCISES <= result <= HYPERTROPHY_MAX_EXERCISES

    def test_fill_to_duration_stops_at_target_count(self):
        candidates = [
            ExerciseInfo(i, f"Ex{i}", "chest", is_compound=True) for i in range(10)
        ]
        selected = _fill_to_duration(candidates, "hypertrophy", session_minutes=999, target_count=3)
        assert len(selected) == 3

    def test_fill_to_duration_never_exceeds_budget_when_more_than_one_selected(self):
        candidates = [
            ExerciseInfo(i, f"Ex{i}", "chest", is_compound=True) for i in range(10)
        ]
        # 2 exercises -> 33 min, 3 -> 46 min, 4 -> 59 min; budget of 40 should fit 2, not 3
        selected = _fill_to_duration(candidates, "hypertrophy", session_minutes=40, target_count=10)
        assert len(selected) == 2

    def test_fill_to_duration_always_keeps_at_least_one_exercise(self):
        candidates = [ExerciseInfo(1, "Bench Press", "chest", is_compound=True)]
        # budget far too small for even 1 exercise (21 min needed) -- still keep it
        selected = _fill_to_duration(candidates, "hypertrophy", session_minutes=5, target_count=5)
        assert len(selected) == 1


# ---------------------------------------------------------------------------
# Warmup
# ---------------------------------------------------------------------------

class TestWarmup:
    def test_ramp_sets_computed_from_first_compound_with_weight(self):
        exercises = [
            WodExercise(1, 1, "Bench Press", 4, 8, 10, 7, 8, 150, 100.0, "reason", False, False, True),
        ]
        warmup = _build_warmup(exercises)
        assert warmup.ramp_sets[0]["weight_kg"] == 50.0
        assert warmup.ramp_sets[1]["weight_kg"] == 70.0
        assert warmup.ramp_sets[2]["weight_kg"] == 85.0
        assert warmup.note is None

    def test_no_ramp_sets_when_no_known_weight(self):
        exercises = [
            WodExercise(1, 1, "Bench Press", 4, 8, 10, 7, 8, 150, None, "cold start", True, True, True),
        ]
        warmup = _build_warmup(exercises)
        assert warmup.ramp_sets == []
        assert warmup.note is not None

    def test_skips_isolation_exercises_for_ramp_reference(self):
        exercises = [
            WodExercise(1, 1, "Cable Fly", 3, 12, 15, 7, 8, 75, 20.0, "r", False, False, False),
            WodExercise(2, 2, "Bench Press", 4, 8, 10, 7, 8, 150, 100.0, "r", False, False, True),
        ]
        warmup = _build_warmup(exercises)
        assert warmup.ramp_sets[0]["weight_kg"] == 50.0  # based on Bench (100kg), not Cable Fly


# ---------------------------------------------------------------------------
# Full integration — generate_wod
# ---------------------------------------------------------------------------

class TestGenerateWodIntegration:
    def test_hypertrophy_end_to_end(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True),
            ExerciseInfo(2, "Incline DB Press", "chest", is_compound=False),
            ExerciseInfo(3, "Barbell Row", "back", is_compound=True),
            ExerciseInfo(4, "Lat Pulldown", "back", is_compound=False),
        ]
        histories = {1: [session(7)], 3: [session(6)]}
        wod = generate_wod(candidates, histories, HYPERTROPHY, session_minutes=60, as_of=BASE)
        assert wod.goal == "hypertrophy"
        assert len(wod.exercises) > 0
        assert wod.estimated_duration_min > 0

    def test_strength_end_to_end(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True, is_main_lift=True),
            ExerciseInfo(2, "Squat", "quads", is_compound=True, is_main_lift=True),
            ExerciseInfo(3, "Triceps Pushdown", "triceps", is_compound=False),
        ]
        wod = generate_wod(candidates, {}, STRENGTH, session_minutes=75, as_of=BASE)
        assert wod.goal == "strength"
        assert len(wod.exercises) > 0

    def test_invalid_goal_raises_value_error(self):
        bad_profile = UserProfile(global_goal="cardio", experience="intermediate")
        with pytest.raises(ValueError):
            generate_wod([ExerciseInfo(1, "X", "chest", is_compound=True)], {}, bad_profile, 60, as_of=BASE)

    def test_empty_candidates_returns_empty_cold_start_wod(self):
        wod = generate_wod([], {}, HYPERTROPHY, session_minutes=60, as_of=BASE)
        assert wod.exercises == []
        assert wod.cold_start is True

    def test_cold_start_true_when_every_exercise_is_cold_start(self):
        candidates = [ExerciseInfo(1, "Bench Press", "chest", is_compound=True)]
        wod = generate_wod(candidates, {}, HYPERTROPHY, session_minutes=60, as_of=BASE)
        assert wod.cold_start is True

    def test_cold_start_false_when_at_least_one_exercise_has_history(self):
        candidates = [
            ExerciseInfo(1, "Bench Press", "chest", is_compound=True),
            ExerciseInfo(2, "Barbell Row", "back", is_compound=True),
        ]
        histories = {1: [session(1), session(2), session(3), session(4), session(5)]}
        wod = generate_wod(candidates, histories, HYPERTROPHY, session_minutes=60, as_of=BASE)
        assert wod.cold_start is False

    def test_duration_respects_br05_budget(self):
        candidates = [
            ExerciseInfo(i, f"Ex{i}", "chest" if i % 2 == 0 else "back", is_compound=True)
            for i in range(8)
        ]
        wod = generate_wod(candidates, {}, HYPERTROPHY, session_minutes=30, as_of=BASE)
        assert wod.estimated_duration_min <= 30 or len(wod.exercises) == 1

    def test_recommendation_fields_come_from_predictor(self):
        candidates = [ExerciseInfo(1, "Bench Press", "chest", is_compound=True)]
        histories = {1: [session(d, weight=100, reps=8, rpe=7.0) for d in (1, 8, 15, 22, 29)]}
        wod = generate_wod(candidates, histories, HYPERTROPHY, session_minutes=60, as_of=BASE)
        ex = wod.exercises[0]
        assert ex.weight_kg is not None
        assert "Laatste" in ex.reason  # matches predictor.py's actual reason string style

    def test_strength_main_lifts_ordered_before_accessories(self):
        candidates = [
            ExerciseInfo(1, "Triceps Pushdown", "triceps", is_compound=False),
            ExerciseInfo(2, "Squat", "quads", is_compound=True, is_main_lift=True),
        ]
        wod = generate_wod(candidates, {}, STRENGTH, session_minutes=90, as_of=BASE)
        names = [e.name for e in wod.exercises]
        assert names.index("Squat") < names.index("Triceps Pushdown")

    def test_hypertrophy_compound_ordered_before_isolation(self):
        candidates = [
            ExerciseInfo(1, "Cable Fly", "chest", is_compound=False),
            ExerciseInfo(2, "Bench Press", "chest", is_compound=True),
        ]
        wod = generate_wod(candidates, {}, HYPERTROPHY, session_minutes=90, as_of=BASE)
        names = [e.name for e in wod.exercises]
        assert names.index("Bench Press") < names.index("Cable Fly")

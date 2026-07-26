"""
tests/test_predictor.py
------------------------
Coverage for engine/predictor.py. Organized by white paper section so any
future spec change points straight at the tests that need revisiting.

Synthetic histories only — no database, no Flask app — matching the
"pure functions" design of predictor.py itself.
"""

from datetime import date, timedelta

import pytest

from engine.predictor import (
    SetLog,
    SessionLog,
    Advice,
    ExerciseProfile,
    UserProfile,
    get_recommendation,
    recommend_hypertrophy,
    recommend_strength,
    recommend_linear,
    brzycki,
    round_to_plate,
    regression_slope,
    regression_predict_next,
    regression_slope_over_days,
    deload_streak_triggered,
    clamp_weight_change,
    linear_progression_failing,
    apply_recovery_adjustment,
    scale_advice_for_experience,
    filter_recent_sessions,
    hypertrophy_rep_range,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

BASE_DATE = date(2026, 1, 5)  # a Monday, arbitrary anchor


def session(days_offset: int, weight: float, reps: int, rpe: float | None, is_warmup=False):
    """Shorthand for building one SessionLog with a single working set,
    which covers the overwhelming majority of test scenarios below."""
    return SessionLog(
        performed_at=BASE_DATE + timedelta(days=days_offset),
        sets=[SetLog(weight_kg=weight, reps=reps, rpe=rpe, is_warmup=is_warmup)],
    )


HYPERTROPHY_COMPOUND = ExerciseProfile(is_compound=True, is_upper_body=True, is_barbell=True)
HYPERTROPHY_ISOLATION = ExerciseProfile(is_compound=False, is_upper_body=True, is_barbell=False)
STRENGTH_LIFT = ExerciseProfile(is_compound=True, is_upper_body=True, is_barbell=True)

INTERMEDIATE_HYPERTROPHY = UserProfile(global_goal="hypertrophy", experience="intermediate")
INTERMEDIATE_STRENGTH = UserProfile(global_goal="strength", experience="intermediate")
BEGINNER_HYPERTROPHY = UserProfile(global_goal="hypertrophy", experience="beginner")
ADVANCED_STRENGTH = UserProfile(global_goal="strength", experience="advanced")


# ---------------------------------------------------------------------------
# §5.8 Cold start
# ---------------------------------------------------------------------------

class TestColdStart:
    def test_zero_sessions_hypertrophy_returns_no_weight(self):
        advice = get_recommendation([], INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg is None
        assert advice.cold_start is True
        assert advice.provisional is True
        assert "startgewicht" in advice.reason.lower()

    def test_zero_sessions_strength_returns_no_weight(self):
        advice = get_recommendation([], INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        assert advice.weight_kg is None
        assert advice.cold_start is True

    def test_zero_sessions_hypertrophy_reps_use_goal_rep_range(self):
        advice = get_recommendation([], INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert (advice.reps_min, advice.reps_max) == (8, 12)

    def test_one_to_four_sessions_marked_provisional(self):
        sessions = [session(i * 7, 100, 8, 7) for i in range(3)]
        advice = get_recommendation(
            sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND,
            as_of=BASE_DATE + timedelta(days=21),
        )
        assert advice.provisional is True
        assert advice.cold_start is False  # there IS history, just not enough yet

    def test_five_or_more_sessions_not_provisional(self):
        sessions = [session(i * 7, 100, 8, 7) for i in range(5)]
        advice = get_recommendation(
            sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND,
            as_of=BASE_DATE + timedelta(days=35),
        )
        assert advice.provisional is False


# ---------------------------------------------------------------------------
# §5.3 / §8.1 Hypertrophy double progression
# ---------------------------------------------------------------------------

class TestHypertrophyDoubleProgression:
    def test_phase1_reps_increase_when_below_ceiling(self):
        sessions = [session(0, 100, 8, 7)]
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg == 100
        assert advice.reps_max == 10  # min(8+2, 12)
        assert advice.deload is False

    def test_phase2_weight_increases_when_ceiling_reached(self):
        sessions = [session(0, 100, 12, 7)]  # already at compound ceiling
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg == pytest.approx(102.5)
        assert advice.reps_min == 8  # reset to floor
        assert "gewicht" in advice.reason.lower()

    def test_isolation_exercise_uses_wider_rep_range(self):
        sessions = [session(0, 20, 14, 7)]
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_ISOLATION)
        floor, ceiling = hypertrophy_rep_range(is_compound=False)
        assert (floor, ceiling) == (12, 15)
        # 14 reps is one below the 15-rep ceiling, so the +2 step gets
        # capped at 15 — the range collapses to a single target, correctly
        # signaling "one more rep and you graduate to more weight."
        assert advice.reps_max == 15
        assert advice.deload is False

    def test_rpe_at_or_above_9_5_consolidates_instead_of_progressing(self):
        sessions = [session(0, 100, 8, 9.5)]
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg == 100
        assert advice.reps_min == advice.reps_max == 8  # repeat exactly, no push
        assert "maximaal" in advice.reason.lower()

    def test_low_rpe_at_ceiling_triggers_fast_track_five_percent(self):
        sessions = [session(0, 100, 12, 6)]  # at ceiling, felt easy
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg == pytest.approx(105.0)

    def test_no_working_sets_falls_back_to_provisional(self):
        sessions = [session(0, 100, 8, 7, is_warmup=True)]  # only a warmup logged
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg is None
        assert advice.provisional is True


# ---------------------------------------------------------------------------
# BR-04 Deload streak (applies across all three strategies)
# ---------------------------------------------------------------------------

class TestDeloadStreak:
    def test_three_consecutive_high_rpe_sessions_triggers_deload_hypertrophy(self):
        sessions = [session(i * 7, 100, 8, 9) for i in range(3)]
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.deload is True
        assert advice.weight_kg < 100  # meaningful drop, not a progression

    def test_three_consecutive_high_rpe_sessions_triggers_deload_strength(self):
        sessions = [session(i * 7, 150, 5, 9.5) for i in range(3)]
        advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        assert advice.deload is True

    def test_three_consecutive_high_rpe_sessions_triggers_deload_linear(self):
        sessions = [session(i * 7, 60, 5, 9) for i in range(3)]
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.deload is True

    def test_deload_never_progresses_weight_upward(self):
        sessions = [session(i * 7, 100, 8, 9.5) for i in range(4)]
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg < 100

    def test_streak_broken_by_one_lower_rpe_session_does_not_deload(self):
        sessions = [
            session(0, 100, 8, 9.5),
            session(7, 100, 8, 7.0),   # breaks the streak
            session(14, 100, 8, 9.5),
        ]
        advice = deload_streak_triggered(sessions)
        assert advice is False

    def test_missing_rpe_in_streak_does_not_force_deload(self):
        sessions = [
            session(0, 100, 8, 9.5),
            session(7, 100, 8, None),  # unlogged RPE shouldn't count toward the streak
            session(14, 100, 8, 9.5),
        ]
        assert deload_streak_triggered(sessions) is False

    def test_fewer_than_three_sessions_cannot_trigger_deload(self):
        sessions = [session(0, 100, 8, 9.8), session(7, 100, 8, 9.9)]
        assert deload_streak_triggered(sessions) is False


# ---------------------------------------------------------------------------
# §5.4 Strength autoregulation
# ---------------------------------------------------------------------------

class TestStrengthAutoregulation:
    def test_low_rpe_positive_trend_progresses_two_point_five_percent(self):
        # rising e1RM series so trend >= 0, last RPE <= 8
        sessions = [session(i * 7, 140 + i, 5, 7.5) for i in range(6)]
        advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        last_weight = sessions[-1].sets[0].weight_kg
        assert advice.weight_kg == pytest.approx(round_to_plate(last_weight * 1.025))
        assert advice.deload is False

    def test_rpe_nine_or_above_holds_weight_without_streak(self):
        sessions = [
            session(0, 140, 5, 7),
            session(7, 140, 5, 9.2),  # only one high-RPE session, not a streak
        ]
        advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        assert advice.weight_kg == 140
        assert advice.deload is False

    def test_flat_trend_moderate_rpe_consolidates(self):
        # avg_rpe between 8 and 9 (exclusive of both branches) -> consolidate
        sessions = [session(i * 7, 140, 5, 8.5) for i in range(6)]
        advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        assert advice.weight_kg == 140
        assert "consolideren" in advice.reason.lower()

    def test_negative_trend_blocks_progression_even_at_low_rpe(self):
        # e1RM declining across sessions despite RPE <= 8
        sessions = [session(i * 7, 150 - i * 2, 5, 7.5) for i in range(6)]
        advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        last_weight = sessions[-1].sets[0].weight_kg
        assert advice.weight_kg == last_weight  # held, not increased

    def test_no_valid_set_under_ten_reps_is_provisional(self):
        sessions = [session(0, 60, 15, 7)]  # high-rep set, no e1RM possible (BR-07)
        advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        assert advice.weight_kg is None
        assert advice.provisional is True


# ---------------------------------------------------------------------------
# §8.2 Beginner linear progression
# ---------------------------------------------------------------------------

class TestLinearProgression:
    def test_upper_body_increments_two_point_five_kg(self):
        sessions = [session(0, 40, 5, 7)]
        upper = ExerciseProfile(is_compound=True, is_upper_body=True)
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, upper)
        assert advice.weight_kg == pytest.approx(42.5)

    def test_lower_body_increments_five_kg(self):
        sessions = [session(0, 60, 5, 7)]
        lower = ExerciseProfile(is_compound=True, is_upper_body=False)
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, lower)
        assert advice.weight_kg == pytest.approx(65.0)

    def test_holds_weight_when_rpe_too_high(self):
        sessions = [session(0, 60, 5, 8.5)]
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, STRENGTH_LIFT)
        assert advice.weight_kg == 60

    def test_two_consecutive_misses_flags_strategy_switch(self):
        exercise = ExerciseProfile(is_compound=True, is_upper_body=True, linear_target_reps=5)
        sessions = [
            session(0, 60, 5, 7),   # hit the target
            session(7, 60, 3, 8),   # missed
            session(14, 60, 3, 8),  # missed again -> two in a row
        ]
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, exercise)
        assert advice.strategy_switch_recommended == "double_progression"

    def test_single_miss_does_not_flag_switch(self):
        sessions = [
            session(0, 60, 5, 7),
            session(7, 60, 3, 8),  # one miss only
        ]
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, STRENGTH_LIFT)
        assert advice.strategy_switch_recommended is None

    def test_linear_progression_failing_helper_directly(self):
        sessions = [session(0, 60, 3, 8), session(7, 60, 4, 8)]
        assert linear_progression_failing(sessions, target_reps=5) is True
        assert linear_progression_failing(sessions, target_reps=3) is False


# ---------------------------------------------------------------------------
# BR-03 Weight change clamp
# ---------------------------------------------------------------------------

class TestWeightClamp:
    def test_clamp_allows_small_increase(self):
        assert clamp_weight_change(102.5, 100) == pytest.approx(102.5)

    def test_clamp_blocks_large_increase(self):
        assert clamp_weight_change(150, 100) == pytest.approx(105.0)

    def test_clamp_blocks_large_decrease(self):
        assert clamp_weight_change(50, 100) == pytest.approx(95.0)

    def test_clamp_is_a_noop_within_bounds(self):
        assert clamp_weight_change(103, 100) == 103

    def test_deload_is_exempt_from_clamp_via_end_to_end_advice(self):
        # a 35% drop would normally violate BR-03, but deloads are exempt
        sessions = [session(i * 7, 100, 8, 9.5) for i in range(3)]
        advice = recommend_hypertrophy(sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND)
        assert advice.weight_kg == pytest.approx(65.0)  # 100 * 0.65, unclamped


# ---------------------------------------------------------------------------
# BR-06 Regression threshold + §5.7 trend
# ---------------------------------------------------------------------------

class TestRegression:
    def test_fewer_than_five_points_returns_none(self):
        assert regression_slope([100, 101, 102, 103]) is None

    def test_five_points_rising_returns_positive_slope(self):
        slope = regression_slope([100, 102, 104, 106, 108])
        assert slope > 0

    def test_five_points_flat_returns_near_zero_slope(self):
        slope = regression_slope([100, 100, 100, 100, 100])
        assert slope == pytest.approx(0, abs=1e-6)

    def test_five_points_declining_returns_negative_slope(self):
        slope = regression_slope([110, 108, 106, 104, 102])
        assert slope < 0

    def test_predict_next_extrapolates_forward(self):
        prediction = regression_predict_next([100, 102, 104, 106, 108])
        assert prediction == pytest.approx(110, abs=0.5)

    def test_predict_next_none_below_threshold(self):
        assert regression_predict_next([100, 102]) is None

    def test_slope_over_days_rising(self):
        # 5 points, roughly +1 per day
        points = [(0, 100), (7, 107), (14, 114), (21, 121), (28, 128)]
        slope = regression_slope_over_days(points)
        assert slope == pytest.approx(1.0, abs=0.01)

    def test_slope_over_days_none_below_five_points(self):
        assert regression_slope_over_days([(0, 100), (7, 101)]) is None


# ---------------------------------------------------------------------------
# BR-07 e1RM validity (Brzycki)
# ---------------------------------------------------------------------------

class TestBrzycki:
    def test_e1rm_none_above_ten_reps(self):
        assert brzycki(100, 12) is None

    def test_e1rm_calculated_at_exactly_ten_reps(self):
        assert brzycki(100, 10) is not None
        assert brzycki(100, 10) == pytest.approx(100 * 36 / 27)

    def test_e1rm_at_one_rep_equals_weight(self):
        assert brzycki(150, 1) == 150

    def test_e1rm_none_for_zero_reps(self):
        assert brzycki(100, 0) is None

    def test_session_e1rm_uses_heaviest_valid_set(self):
        s = SessionLog(BASE_DATE, sets=[
            SetLog(80, 15, 7),   # too many reps, invalid for e1RM
            SetLog(100, 5, 8),   # valid, should be used
        ])
        assert s.e1rm() == pytest.approx(brzycki(100, 5))


# ---------------------------------------------------------------------------
# BR-08 Warmup exclusion + §5.9 outlier/staleness filtering
# ---------------------------------------------------------------------------

class TestDataQuality:
    def test_warmup_sets_excluded_from_best_set(self):
        s = SessionLog(BASE_DATE, sets=[
            SetLog(120, 3, None, is_warmup=True),
            SetLog(100, 8, 7, is_warmup=False),
        ])
        assert s.best_set().weight_kg == 100

    def test_warmup_sets_excluded_from_tonnage(self):
        s = SessionLog(BASE_DATE, sets=[
            SetLog(120, 3, None, is_warmup=True),
            SetLog(100, 8, 7, is_warmup=False),
        ])
        assert s.tonnage() == 800  # only the working set counts

    def test_reps_over_thirty_excluded_as_outlier(self):
        s = SessionLog(BASE_DATE, sets=[SetLog(20, 45, 8)])
        assert s.working_sets() == []
        assert s.best_set() is None

    def test_missing_rpe_excluded_from_average_but_set_still_counts_for_tonnage(self):
        s = SessionLog(BASE_DATE, sets=[
            SetLog(100, 8, None),
            SetLog(100, 8, 7),
        ])
        assert s.avg_rpe() == 7  # only the logged RPE contributes
        assert s.tonnage() == 1600  # both sets still count toward tonnage

    def test_sessions_older_than_ninety_days_are_filtered_out(self):
        old = session(-100, 100, 8, 7)
        recent = session(-10, 105, 8, 7)
        filtered = filter_recent_sessions([old, recent], as_of=BASE_DATE)
        assert old not in filtered
        assert recent in filtered

    def test_stale_history_forces_cold_start_style_provisional(self):
        old_sessions = [session(-100 - i * 7, 100, 8, 7) for i in range(6)]
        advice = get_recommendation(
            old_sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND, as_of=BASE_DATE
        )
        assert advice.cold_start is True  # zero *recent* sessions survive the filter


# ---------------------------------------------------------------------------
# §8.8 Recovery adjustment
# ---------------------------------------------------------------------------

class TestRecoveryAdjustment:
    def test_poor_sleep_suppresses_increase_and_lowers_rpe_target(self):
        last = session(0, 100, 12, 7)
        base_advice = Advice(
            weight_kg=102.5, reps_min=8, reps_max=10,
            rpe_target_min=7, rpe_target_max=8, reason="baseline",
        )
        profile = UserProfile(global_goal="hypertrophy", sleep_score=1)
        adjusted = apply_recovery_adjustment(base_advice, last, profile)
        assert adjusted.weight_kg == 100  # increase suppressed -> hold
        assert adjusted.rpe_target_min == 6
        assert "herstel-check-in" in adjusted.reason

    def test_high_stress_also_triggers_adjustment(self):
        last = session(0, 100, 12, 7)
        base_advice = Advice(
            weight_kg=102.5, reps_min=8, reps_max=10,
            rpe_target_min=7, rpe_target_max=8, reason="baseline",
        )
        profile = UserProfile(global_goal="hypertrophy", stress_score=5)
        adjusted = apply_recovery_adjustment(base_advice, last, profile)
        assert adjusted.weight_kg == 100

    def test_good_recovery_leaves_advice_untouched(self):
        last = session(0, 100, 12, 7)
        base_advice = Advice(
            weight_kg=102.5, reps_min=8, reps_max=10,
            rpe_target_min=7, rpe_target_max=8, reason="baseline",
        )
        profile = UserProfile(global_goal="hypertrophy", sleep_score=4, stress_score=2)
        adjusted = apply_recovery_adjustment(base_advice, last, profile)
        assert adjusted.weight_kg == 102.5
        assert adjusted.reason == "baseline"

    def test_recovery_adjustment_does_not_override_deload(self):
        base_advice = Advice(
            weight_kg=65, reps_min=8, reps_max=8,
            rpe_target_min=5, rpe_target_max=6, reason="deload", deload=True,
        )
        profile = UserProfile(global_goal="hypertrophy", sleep_score=1)
        adjusted = apply_recovery_adjustment(base_advice, session(0, 100, 8, 9.5), profile)
        assert adjusted.weight_kg == 65  # untouched


# ---------------------------------------------------------------------------
# §8.9 Experience-based dampening
# ---------------------------------------------------------------------------

class TestExperienceScaling:
    def test_advanced_lifter_gets_smaller_increment_than_intermediate(self):
        sessions = [session(i * 7, 140 + i, 5, 7.5) for i in range(6)]
        intermediate_advice = recommend_strength(sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT)
        advanced_advice = recommend_strength(sessions, ADVANCED_STRENGTH, STRENGTH_LIFT)
        last_weight = sessions[-1].sets[0].weight_kg

        scaled = scale_advice_for_experience(advanced_advice, last_weight, STRENGTH_LIFT, ADVANCED_STRENGTH)
        intermediate_delta = intermediate_advice.weight_kg - last_weight
        advanced_delta = scaled.weight_kg - last_weight
        assert 0 < advanced_delta < intermediate_delta

    def test_beginner_experience_untouched_by_dampening(self):
        base_advice = Advice(
            weight_kg=102.5, reps_min=8, reps_max=8,
            rpe_target_min=7, rpe_target_max=8, reason="x",
        )
        profile = UserProfile(global_goal="hypertrophy", experience="beginner")
        result = scale_advice_for_experience(base_advice, 100, STRENGTH_LIFT, profile)
        assert result.weight_kg == 102.5  # unchanged — beginners don't use this path

    def test_dampening_skips_deloads(self):
        base_advice = Advice(
            weight_kg=65, reps_min=8, reps_max=8,
            rpe_target_min=5, rpe_target_max=6, reason="deload", deload=True,
        )
        result = scale_advice_for_experience(base_advice, 100, STRENGTH_LIFT, ADVANCED_STRENGTH)
        assert result.weight_kg == 65


# ---------------------------------------------------------------------------
# BR-02 + dispatcher integration (get_recommendation end-to-end)
# ---------------------------------------------------------------------------

class TestDispatcherIntegration:
    def test_beginner_routed_to_linear_regardless_of_goal(self):
        sessions = [session(i * 7, 60, 5, 7) for i in range(2)]
        advice = get_recommendation(
            sessions, BEGINNER_HYPERTROPHY, STRENGTH_LIFT, as_of=BASE_DATE + timedelta(days=14)
        )
        assert "lineaire" in advice.reason.lower()

    def test_intermediate_hypertrophy_routed_to_double_progression(self):
        sessions = [session(i * 7, 100, 12, 7) for i in range(2)]
        advice = get_recommendation(
            sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND,
            as_of=BASE_DATE + timedelta(days=14),
        )
        assert "rep-range" in advice.reason.lower()

    def test_intermediate_strength_routed_to_autoregulation(self):
        sessions = [session(i * 7, 140, 5, 7.5) for i in range(6)]
        advice = get_recommendation(
            sessions, INTERMEDIATE_STRENGTH, STRENGTH_LIFT,
            as_of=BASE_DATE + timedelta(days=42),
        )
        assert advice.weight_kg is not None
        assert advice.weight_kg >= 140

    def test_invalid_goal_raises_value_error(self):
        bad_profile = UserProfile(global_goal="endurance", experience="intermediate")  # type: ignore
        with pytest.raises(ValueError):
            get_recommendation([session(0, 100, 8, 7)], bad_profile, HYPERTROPHY_COMPOUND)

    def test_every_advice_has_a_reason_br01(self):
        """BR-01 smoke test across a handful of representative scenarios."""
        scenarios = [
            ([], INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND),
            ([session(0, 100, 8, 7)], INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND),
            ([session(0, 140, 5, 7)], INTERMEDIATE_STRENGTH, STRENGTH_LIFT),
            ([session(0, 60, 5, 7)], BEGINNER_HYPERTROPHY, HYPERTROPHY_COMPOUND),
        ]
        for hist, profile, ex in scenarios:
            advice = get_recommendation(hist, profile, ex, as_of=BASE_DATE)
            assert advice.reason and len(advice.reason) > 0

    def test_full_pipeline_never_exceeds_five_percent_jump_outside_deload(self):
        sessions = [session(i * 7, 100, 12, 6) for i in range(6)]  # fast-track eligible
        advice = get_recommendation(
            sessions, INTERMEDIATE_HYPERTROPHY, HYPERTROPHY_COMPOUND,
            as_of=BASE_DATE + timedelta(days=42),
        )
        assert advice.weight_kg <= 100 * 1.05 + 0.01  # tiny epsilon for plate rounding


# ---------------------------------------------------------------------------
# Coverage gap-fillers — small, genuine branches pytest-cov flagged as untested
# rather than padding for a number.
# ---------------------------------------------------------------------------

class TestRemainingBranches:
    def test_round_to_plate_dumbbell_step_is_two_kg(self):
        assert round_to_plate(31, is_barbell=False) == 32  # nearest 2kg step

    def test_rpe_target_display_single_value(self):
        advice = Advice(weight_kg=100, reps_min=8, reps_max=8, rpe_target_min=8, rpe_target_max=8, reason="x")
        assert advice.rpe_target_display() == "RPE 8"

    def test_rpe_target_display_range(self):
        advice = Advice(weight_kg=100, reps_min=8, reps_max=8, rpe_target_min=7, rpe_target_max=8, reason="x")
        assert advice.rpe_target_display() == "RPE 7-8"

    def test_linear_progression_failing_false_when_a_session_has_no_working_sets(self):
        sessions = [
            SessionLog(BASE_DATE, sets=[SetLog(60, 5, 7, is_warmup=True)]),  # only a warmup
            session(7, 60, 3, 8),
        ]
        assert linear_progression_failing(sessions, target_reps=5) is False

    def test_recommend_linear_no_working_sets_falls_back_to_provisional(self):
        sessions = [SessionLog(BASE_DATE, sets=[SetLog(60, 5, 7, is_warmup=True)])]
        advice = recommend_linear(sessions, BEGINNER_HYPERTROPHY, STRENGTH_LIFT)
        assert advice.weight_kg is None
        assert advice.provisional is True

    def test_scale_advice_for_experience_noop_when_not_actually_increasing(self):
        # a hold/consolidate advice (weight unchanged) shouldn't be touched
        base_advice = Advice(
            weight_kg=100, reps_min=5, reps_max=5,
            rpe_target_min=8, rpe_target_max=8, reason="consolideren",
        )
        result = scale_advice_for_experience(base_advice, last_weight=100, exercise=STRENGTH_LIFT, profile=ADVANCED_STRENGTH)
        assert result.weight_kg == 100

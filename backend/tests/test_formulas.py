"""Tests for engine/formulas.py — pure functions, no DB needed."""
from engine.formulas import brzycki_e1rm, tonnage, round_to_plate, tut_sec, weight_jump_is_suspicious


def test_brzycki_known_value():
    # 100kg x 5 reps -> 36/(37-5) = 1.125 -> 112.5 kg
    assert brzycki_e1rm(100, 5) == 112.5


def test_brzycki_single_rep_returns_weight():
    assert brzycki_e1rm(140, 1) == 140


def test_brzycki_rejects_above_ten_reps():
    assert brzycki_e1rm(50, 11) is None  # BR-07


def test_brzycki_rejects_zero_reps():
    assert brzycki_e1rm(50, 0) is None


def test_tonnage_basic():
    assert tonnage(100, 5) == 500


def test_round_to_plate_barbell():
    assert round_to_plate(101.3) == 102.5
    assert round_to_plate(98.6) == 97.5


def test_round_to_plate_dumbbell():
    assert round_to_plate(21.4, unit="db") == 22.0


def test_tut_sec_basic():
    # 8 reps, tempo 2-0-1-0 -> 8 * (2+0+1+0) = 24
    assert tut_sec(8, "2-0-1-0") == 24


def test_tut_sec_missing_tempo():
    assert tut_sec(8, None) is None


def test_tut_sec_malformed_tempo():
    assert tut_sec(8, "not-a-tempo") is None


def test_weight_jump_flags_over_20_percent():
    assert weight_jump_is_suspicious(130, 100) is True  # +30%


def test_weight_jump_allows_normal_progression():
    assert weight_jump_is_suspicious(102.5, 100) is False  # +2.5%


def test_weight_jump_no_previous_data():
    assert weight_jump_is_suspicious(100, None) is False

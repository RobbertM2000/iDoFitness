"""SQLAlchemy models — implements White Paper chapter 9 one-to-one.

Conventions (White Paper §9):
- every table: id (PK) + created_at
- soft deletes via deleted_at on user-facing data (workouts, sets)
- ON DELETE CASCADE from user to all owned data (GDPR erasure, §17)
- business rules referenced as BR-xx (White Paper appendix A)
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint, Index
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


# ---------------------------------------------------------------- users

class User(TimestampMixin, UserMixin, db.Model):
    __tablename__ = "users"

    username = db.Column(db.String(30), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(50))

    age = db.Column(db.SmallInteger)
    height_cm = db.Column(db.SmallInteger)
    bodyweight_kg = db.Column(db.Numeric(5, 1))
    sex = db.Column(db.String(20))

    global_goal = db.Column(db.String(12), nullable=False, default="hypertrophy")
    experience = db.Column(db.String(12))
    days_per_week = db.Column(db.SmallInteger)
    session_minutes = db.Column(db.SmallInteger)
    training_location = db.Column(db.String(10))
    unit_preference = db.Column(db.String(3), default="kg")

    deload_active = db.Column(db.Boolean, default=False, nullable=False)
    last_deload_at = db.Column(db.Date)
    sleep_score = db.Column(db.SmallInteger)
    stress_score = db.Column(db.SmallInteger)

    onboarding_completed = db.Column(db.Boolean, default=False, nullable=False)
    plan = db.Column(db.String(10), default="free", nullable=False)  # §19, no logic in v1

    workouts = db.relationship(
        "Workout", backref="user", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("age BETWEEN 16 AND 100", name="ck_users_age"),
        CheckConstraint(
            "global_goal IN ('hypertrophy','strength')", name="ck_users_goal"  # BR-02
        ),
        CheckConstraint(
            "experience IN ('beginner','intermediate','advanced')",
            name="ck_users_experience",
        ),
        CheckConstraint("days_per_week BETWEEN 1 AND 7", name="ck_users_days"),
    )

    # --- password helpers (White Paper §10.3: werkzeug PBKDF2-SHA256) ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def to_public_dict(self) -> dict:
        """Fields safe to send to the client (never password_hash)."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "age": self.age,
            "height_cm": self.height_cm,
            "bodyweight_kg": float(self.bodyweight_kg) if self.bodyweight_kg is not None else None,
            "sex": self.sex,
            "global_goal": self.global_goal,
            "experience": self.experience,
            "days_per_week": self.days_per_week,
            "session_minutes": self.session_minutes,
            "training_location": self.training_location,
            "onboarding_completed": self.onboarding_completed,
            "unit_preference": self.unit_preference,
        }


# ------------------------------------------------- reference tables

class MuscleGroup(TimestampMixin, db.Model):
    __tablename__ = "muscle_groups"
    name = db.Column(db.String(30), unique=True, nullable=False)


class Equipment(TimestampMixin, db.Model):
    __tablename__ = "equipment"
    name = db.Column(db.String(30), unique=True, nullable=False)


class UserEquipment(TimestampMixin, db.Model):
    __tablename__ = "user_equipment"
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id = db.Column(
        db.Integer, db.ForeignKey("equipment.id"), nullable=False
    )
    __table_args__ = (UniqueConstraint("user_id", "equipment_id", name="uq_user_equipment"),)


# ---------------------------------------------------------- exercises

class Exercise(TimestampMixin, db.Model):
    __tablename__ = "exercises"

    name = db.Column(db.String(80), nullable=False)
    primary_muscle_id = db.Column(
        db.Integer, db.ForeignKey("muscle_groups.id"), nullable=False
    )
    is_compound = db.Column(db.Boolean, nullable=False)
    equipment_id = db.Column(db.Integer, db.ForeignKey("equipment.id"), nullable=False)
    difficulty = db.Column(db.String(12))
    description = db.Column(db.Text)
    technique_tips = db.Column(db.Text)
    common_mistakes = db.Column(db.Text)
    video_url = db.Column(db.Text)
    is_main_lift = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    is_archived = db.Column(db.Boolean, default=False, nullable=False)

    primary_muscle = db.relationship("MuscleGroup")

    __table_args__ = (UniqueConstraint("name", "created_by", name="uq_exercise_name_owner"),)


class ExerciseSecondaryMuscle(TimestampMixin, db.Model):
    __tablename__ = "exercise_secondary_muscles"
    exercise_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    muscle_group_id = db.Column(
        db.Integer, db.ForeignKey("muscle_groups.id"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("exercise_id", "muscle_group_id", name="uq_exercise_secondary"),
    )


class ExerciseAlternative(TimestampMixin, db.Model):
    __tablename__ = "exercise_alternatives"
    exercise_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    alternative_id = db.Column(
        db.Integer, db.ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False
    )
    __table_args__ = (
        UniqueConstraint("exercise_id", "alternative_id", name="uq_exercise_alternative"),
    )


class UserAvoidedExercise(TimestampMixin, db.Model):
    __tablename__ = "user_avoided_exercises"
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    reason = db.Column(db.String(120))
    __table_args__ = (UniqueConstraint("user_id", "exercise_id", name="uq_user_avoided"),)


# ----------------------------------------------------------- workouts

class Workout(TimestampMixin, db.Model):
    __tablename__ = "workouts"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    performed_at = db.Column(db.DateTime(timezone=True), nullable=False)
    duration_sec = db.Column(db.Integer)
    title = db.Column(db.String(80))
    notes = db.Column(db.Text)
    source = db.Column(db.String(12))
    client_uuid = db.Column(db.String(36), unique=True)
    deleted_at = db.Column(db.DateTime(timezone=True))
    # Tags a workout with the WOD it was started from (date+goal composite,
    # see api/suggestions.py's `wod_id`) — WODs aren't persisted, so this is
    # a lightweight breadcrumb for analytics later, not a real FK.
    suggested_from_wod_id = db.Column(db.String(40))

    exercises = db.relationship(
        "WorkoutExercise",
        backref="workout",
        cascade="all, delete-orphan",
        order_by="WorkoutExercise.position",
    )

    __table_args__ = (
        CheckConstraint("source IN ('manual','suggested')", name="ck_workouts_source"),
        Index("ix_workouts_user_performed", "user_id", "performed_at"),
    )


class WorkoutExercise(TimestampMixin, db.Model):
    __tablename__ = "workout_exercises"

    workout_id = db.Column(
        db.Integer, db.ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    position = db.Column(db.SmallInteger, nullable=False)
    notes = db.Column(db.Text)

    exercise = db.relationship("Exercise")
    sets = db.relationship(
        "Set", backref="workout_exercise", cascade="all, delete-orphan",
        order_by="Set.set_number",
    )

    __table_args__ = (
        UniqueConstraint("workout_id", "position", name="uq_workout_position"),
    )


class Set(TimestampMixin, db.Model):
    __tablename__ = "sets"

    workout_exercise_id = db.Column(
        db.Integer,
        db.ForeignKey("workout_exercises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    set_number = db.Column(db.SmallInteger, nullable=False)
    weight_kg = db.Column(db.Numeric(6, 2), nullable=False)
    reps = db.Column(db.SmallInteger, nullable=False)
    rpe = db.Column(db.Numeric(3, 1))
    tempo = db.Column(db.String(10))
    tut_sec = db.Column(db.SmallInteger)
    is_warmup = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("weight_kg >= 0", name="ck_sets_weight"),
        CheckConstraint("reps BETWEEN 1 AND 100", name="ck_sets_reps"),
        CheckConstraint("rpe BETWEEN 1 AND 10", name="ck_sets_rpe"),
    )


# ----------------------------------------------- derived data & engine

class E1rmHistory(TimestampMixin, db.Model):
    __tablename__ = "e1rm_history"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    e1rm_kg = db.Column(db.Numeric(6, 2), nullable=False)
    source_set_id = db.Column(db.Integer, db.ForeignKey("sets.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("ix_e1rm_user_exercise_date", "user_id", "exercise_id", "date"),
    )


class PersonalRecord(TimestampMixin, db.Model):
    __tablename__ = "personal_records"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    record_type = db.Column(db.String(12), nullable=False)
    value = db.Column(db.Numeric(8, 2), nullable=False)
    set_id = db.Column(db.Integer, db.ForeignKey("sets.id", ondelete="SET NULL"))
    achieved_at = db.Column(db.Date, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "record_type IN ('weight','reps','e1rm','tonnage')", name="ck_pr_type"
        ),
        UniqueConstraint("user_id", "exercise_id", "record_type", name="uq_pr"),
    )


class Warning(TimestampMixin, db.Model):
    __tablename__ = "warnings"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    warning_type = db.Column(db.String(30), nullable=False)
    message = db.Column(db.Text, nullable=False)
    action_hint = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(10))
    dismissed_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.Date)


class PeriodizationBlock(TimestampMixin, db.Model):
    __tablename__ = "periodization_blocks"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    weeks = db.Column(db.JSON, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)

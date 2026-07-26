"""Idempotent seed data — White Paper §9, §13.

Run with: py -m flask --app app seed
Safe to run repeatedly: checks for existing rows before inserting.
"""
from extensions import db
from models import Equipment, MuscleGroup, Exercise, ExerciseSecondaryMuscle, ExerciseAlternative
from exercise_data import EXERCISES

EQUIPMENT_SEED = [
    "barbell", "dumbbell", "cable", "machine",
    "bodyweight", "band", "rack", "bench",
]

MUSCLE_GROUP_SEED = [
    "chest", "back", "quads", "hamstrings", "glutes",
    "shoulders", "biceps", "triceps", "calves", "abs",
]


def seed_equipment():
    existing = {e.name for e in Equipment.query.all()}
    added = 0
    for name in EQUIPMENT_SEED:
        if name not in existing:
            db.session.add(Equipment(name=name))
            added += 1
    db.session.commit()
    return added


def seed_muscle_groups():
    existing = {m.name for m in MuscleGroup.query.all()}
    added = 0
    for name in MUSCLE_GROUP_SEED:
        if name not in existing:
            db.session.add(MuscleGroup(name=name))
            added += 1
    db.session.commit()
    return added


def seed_exercises():
    """Idempotent: matches on (name, created_by=NULL) per the exercises unique constraint."""
    muscle_by_name = {m.name: m for m in MuscleGroup.query.all()}
    equipment_by_name = {e.name: e for e in Equipment.query.all()}
    existing_names = {
        e.name for e in Exercise.query.filter(Exercise.created_by.is_(None)).all()
    }

    added = 0
    for item in EXERCISES:
        if item["name"] in existing_names:
            continue
        ex = Exercise(
            name=item["name"],
            primary_muscle_id=muscle_by_name[item["muscle"]].id,
            is_compound=item["compound"],
            equipment_id=equipment_by_name[item["equipment"]].id,
            difficulty=item["difficulty"],
            description=item["description"],
            technique_tips="\n".join(item["tips"]),
            common_mistakes="\n".join(item["mistakes"]),
            video_url=f"https://www.youtube.com/results?search_query={item['name'].replace(' ', '+')}+exercise+form",
            is_main_lift=item.get("is_main_lift", False),
            created_by=None,
        )
        db.session.add(ex)
        added += 1
    db.session.commit()

    # Secondary muscles — second pass, now that every exercise has an id.
    exercise_by_name = {e.name: e for e in Exercise.query.filter(Exercise.created_by.is_(None)).all()}
    existing_secondary = {
        (s.exercise_id, s.muscle_group_id) for s in ExerciseSecondaryMuscle.query.all()
    }
    for item in EXERCISES:
        ex = exercise_by_name[item["name"]]
        for sec_name in item.get("secondary", []):
            mg = muscle_by_name.get(sec_name)
            if mg and (ex.id, mg.id) not in existing_secondary:
                db.session.add(ExerciseSecondaryMuscle(exercise_id=ex.id, muscle_group_id=mg.id))
                existing_secondary.add((ex.id, mg.id))
    db.session.commit()

    # Alternatives — symmetric (White Paper §9: "symmetrisch gevuld door seed-script").
    existing_alts = {(a.exercise_id, a.alternative_id) for a in ExerciseAlternative.query.all()}
    for item in EXERCISES:
        ex = exercise_by_name[item["name"]]
        for alt_name in item.get("alternatives", []):
            alt = exercise_by_name.get(alt_name)
            if not alt:
                continue
            for a, b in [(ex.id, alt.id), (alt.id, ex.id)]:
                if (a, b) not in existing_alts:
                    db.session.add(ExerciseAlternative(exercise_id=a, alternative_id=b))
                    existing_alts.add((a, b))
    db.session.commit()

    return added


def register_cli(app):
    @app.cli.command("seed")
    def seed_command():
        """Populate equipment, muscle_groups, and the exercise library."""
        eq = seed_equipment()
        mg = seed_muscle_groups()
        ex = seed_exercises()
        print(f"Seeded {eq} equipment, {mg} muscle groups, {ex} exercises.")

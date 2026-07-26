# iDoFitness

#### Video Demo: https://www.youtube.com/watch?v=-U2PGw6fJVE

#### Description:

iDoFitness is an **evidence-based fitness coaching web application** that combines intelligent workout logging with automated, data-driven training recommendations. The app solves a real problem for intermediate-to-advanced strength athletes: after the beginner phase, progression becomes unpredictable and requires knowledge of periodization, fatigue management, and volume optimization that most lifters lack. iDoFitness bridges that gap by functioning as a personal, AI-powered coach that suggests complete workouts tailored to each user's training history and goals.

## The Problem

Serious lifters hit a wall after their first year of training. Existing apps fall into two camps: **passive loggers** (Strong, Hevy) that record workouts but don't advise what to do next, or **black-box generators** (FitBod) that suggest workouts but hide the reasoning. Static training programs don't adapt to individual variation—a missed session or strength plateau breaks the plan entirely.

**iDoFitness closes this gap** by generating personalized workouts based on each user's own data, using transparent, evidence-based rules grounded in sports science: RPE autoregulation, double progression, volume landmarks, and fatigue detection.

## How It Works

iDoFitness implements a **three-layer recommendation pipeline**:

1. **Per-Exercise Recommendations** (`GET /api/recommendation?exercise_id=X`)
   - Analyzes the user's history for that exercise (last 10 sessions, last 90 days)
   - Applies goal-specific logic (hypertrophy: double progression; strength: RPE autoregulation)
   - Returns: weight, reps, RPE target, and human-readable reason
   - Example: *"Last: 100 kg × 8 @ RPE 7. You have room for 2 more reps."*

2. **Intelligent Exercise Selection** (`engine/wod_generator.py`)
   - Identifies under-trained muscle groups this week
   - Prioritizes compound movements over isolation
   - Respects equipment availability and injury history
   - Selects exercises to fit the user's available time (never exceeds budget)

3. **Complete Workout Generation** (`GET /api/workout-suggestion`)
   - Combines per-exercise advice into a full session plan
   - Determines sets, reps, rest periods based on goal and exercise type
   - Returns warmup protocol, exercise sequence, cooldown, and estimated duration
   - Detects "cold start" (new users/exercises) and handles gracefully

## Key Features

✅ **User Accounts & Profiles** — Registration, login, 8-screen onboarding capturing goal, experience, equipment, availability

✅ **Workout Logger** — Fast mobile-first interface, 59-exercise library with technique tips, automatic PR detection (4 types), warmup exclusion, outlier detection, draft persistence

✅ **Workout Suggestions** — Generates complete workouts matching goal/equipment/time budget; all suggestions are transparent with explanations

✅ **Intelligent Progression** — Hypertrophy (double progression), Strength (RPE-autoregulation), Beginner (linear with auto-switch), recovery-adjusted based on sleep/stress

✅ **Analytics & Dashboards** — Goal-specific views, week-by-week volume tracking, e1RM progression curves with forecasts, muscle-group balance, streak tracking

✅ **Privacy & Security** — PBKDF2-SHA256 hashing, HttpOnly cookies, CSRF protection, GDPR compliance (data export, account deletion), no ads or data sales

## Tech Stack

**Frontend:** React 18 + Vite, CSS variables for theming (light/dark mode), custom-designed components

**Backend:** Flask 3.1 + SQLAlchemy, PostgreSQL, scikit-learn for trend detection

**Testing:** 156 passing tests (169 total), engine modules at 100% coverage, pytest with fixtures and parametrization

**Infrastructure:** GitHub version control, 8+ detailed commits

## How to Run Locally

### Prerequisites
- Python 3.14+
- Node.js 18+
- PostgreSQL 14+

### Backend Setup

```bash
cd backend
py -m pip install -r requirements.txt
createdb idofitness_dev
# Create .env file with: DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/idofitness_dev
py -m flask db upgrade
py -m flask seed
py -m pytest tests/ -v  # Verify all tests pass
py -m flask --app app run --port 5000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Access at `http://localhost:3000`

## Design Decisions

### Evidence-Based Over Black Box

The recommendation engine is **fully transparent and rule-based**, not a neural network. Users see *why* the app suggests a specific weight or rep range. Progression thresholds are tunable constants, not learned parameters. Warnings trigger only when objective conditions are met (e.g., 3+ weeks of zero progress, RPE ≥9.5 in 3 consecutive sessions).

Why? Because lifters deserve to understand their coaching. Black-box recommendations breed distrust.

### Goal-Specific Entire Stack

Rather than one-size-fits-all, the app splits on `global_goal` at every layer:
- **Hypertrophy users** see volume dashboards, rep-range advice, frequency warnings
- **Strength users** see e1RM graphs, intensity/load advice, RPE distribution

This changes which exercises are suggested, which reps/RPE targets, and how progression is modeled.

### Cold-Start Transparency

New users and new exercises have no history. Instead of fabricating recommendations, the API returns `cold_start=true` and `weight_kg=null`, displaying: *"Log this exercise ~5 times for personalized recommendations."* The WOD generator still includes the exercise but says "choose your own weight, RPE 7."

This builds trust faster than guessing.

### White Paper as Specification

I authored a comprehensive **20-chapter white paper** covering product vision, onboarding UX, AI recommendation engine, database schema, API endpoints, frontend architecture, and 12 business rules. Every component was built to this single spec rather than iterative guesswork, ensuring clarity and consistency.

## Testing & Code Quality

- **156 passing tests** across auth, onboarding, exercises, workouts, and engine modules
- **Engine modules at 100% coverage** (predictor.py: 72 tests, wod_generator.py: 36 tests)
- All engine functions are pure (no DB/network calls), making them unit-testable in isolation
- Test files include edge cases: cold start, outliers, ties, weight jumps, malformed input

## Roadmap

**v1 Scope (Current):** Single-user account, warnings on dashboard load, 5+ sessions needed for personalized advice, external video links

**v2+:** Settings screen, web push notifications, native mobile app (React Native), wearable integration, nutrition tracking, computer-vision form check, coach marketplace

## Conclusion

iDoFitness demonstrates **full-stack web development** (React, Flask, PostgreSQL), **software engineering discipline** (testing, documentation, git history), and **domain expertise** (sports science, training periodization). It solves a genuine problem for a real audience: lifters who want data-driven coaching without guessing.

Whether scaled to thousands of users or used as a reference architecture for other coaching applications, iDoFitness proves that **transparent, evidence-based recommendations outperform black-box ML** in domains where users need to understand *why* they're being advised.

---

**GitHub:** https://github.com/RobbertM2000/iDoFitness

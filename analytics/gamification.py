"""
analytics/gamification.py
─────────────────────────
Derives streak / XP / level / badges from real activity tables
(quiz_attempts, mastery_states, learning_sessions, user_profile).

XP model:   10·attempts + 25·correct + 100·concepts_mastered + 200·mocks_completed
Level:      500 XP per level (level = xp // 500 + 1)
Streak:     consecutive days (ending today or yesterday) with >=1 quiz_attempt
            or learning_session.
"""

import os
import sqlite3
import datetime
from typing import Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "gate_mentor.db")

XP_PER_LEVEL = 500


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _active_dates(conn) -> set:
    dates = set()
    for tbl, col in (("quiz_attempts", "timestamp"), ("learning_sessions", "start_time")):
        try:
            rows = conn.execute(f"SELECT DISTINCT DATE({col}) AS d FROM {tbl} WHERE {col} IS NOT NULL").fetchall()
            for r in rows:
                if r["d"]:
                    dates.add(r["d"])
        except sqlite3.Error:
            pass
    return dates


def _streak(active_dates: set, today: datetime.date) -> int:
    if not active_dates:
        return 0
    # Streak counts back from today; allow it to still be "alive" if the last
    # active day was yesterday (today not yet practised).
    anchor = today
    if today.isoformat() not in active_dates:
        if (today - datetime.timedelta(days=1)).isoformat() in active_dates:
            anchor = today - datetime.timedelta(days=1)
        else:
            return 0
    streak = 0
    d = anchor
    while d.isoformat() in active_dates:
        streak += 1
        d -= datetime.timedelta(days=1)
    return streak


def _badges(streak, total_quizzes, mastered, mocks, prob_mastered_all) -> List[Dict[str, Any]]:
    defs = [
        ("first_steps", "First Steps", "Answer your first quiz", "🎯", total_quizzes >= 1),
        ("warming_up", "Warming Up", "Answer 25 quizzes", "🔥", total_quizzes >= 25),
        ("centurion", "Centurion", "Answer 100 quizzes", "💯", total_quizzes >= 100),
        ("on_fire", "On Fire", "Keep a 7-day streak", "⚡", streak >= 7),
        ("unstoppable", "Unstoppable", "Keep a 30-day streak", "🏆", streak >= 30),
        ("first_mastery", "Scholar", "Master your first concept", "📘", mastered >= 1),
        ("bayesian", "Bayesian", "Master all Probability concepts", "🎲", prob_mastered_all),
        ("mock_warrior", "Mock Warrior", "Finish your first mock test", "⚔️", mocks >= 1),
    ]
    return [{"id": i, "title": t, "description": d, "icon": ic, "earned": bool(e)}
            for (i, t, d, ic, e) in defs]


def get_gamification() -> Dict[str, Any]:
    conn = _conn()
    today = datetime.date.today()

    total_quizzes = conn.execute("SELECT COUNT(*) AS c FROM quiz_attempts").fetchone()["c"]
    correct = conn.execute("SELECT COUNT(*) AS c FROM quiz_attempts WHERE is_correct = 1").fetchone()["c"]
    mastered = conn.execute("SELECT COUNT(*) AS c FROM mastery_states WHERE state_level = 8").fetchone()["c"]
    today_attempts = conn.execute(
        "SELECT COUNT(*) AS c FROM quiz_attempts WHERE DATE(timestamp) = ?", (today.isoformat(),)
    ).fetchone()["c"]

    # profile (mocks_completed, daily_goal)
    prof = conn.execute("SELECT mocks_completed, daily_goal FROM user_profile WHERE id = 1").fetchone()
    mocks = prof["mocks_completed"] if prof and prof["mocks_completed"] is not None else 0
    daily_goal = prof["daily_goal"] if prof and prof["daily_goal"] else 10

    # all probability concepts mastered?
    prob_total = conn.execute("SELECT COUNT(*) AS c FROM concepts WHERE concept_id LIKE 'PROB_%'").fetchone()["c"]
    prob_mastered = conn.execute(
        "SELECT COUNT(*) AS c FROM mastery_states m JOIN concepts c ON m.concept_id = c.concept_id "
        "WHERE c.concept_id LIKE 'PROB_%' AND m.state_level = 8"
    ).fetchone()["c"]
    prob_mastered_all = prob_total > 0 and prob_mastered == prob_total

    streak = _streak(_active_dates(conn), today)
    conn.close()

    xp = 10 * total_quizzes + 25 * correct + 100 * mastered + 200 * mocks
    level = xp // XP_PER_LEVEL + 1
    level_progress = (xp % XP_PER_LEVEL) / XP_PER_LEVEL

    badges = _badges(streak, total_quizzes, mastered, mocks, prob_mastered_all)

    return {
        "streak": streak,
        "xp": xp,
        "level": level,
        "level_progress": round(level_progress, 3),
        "xp_into_level": xp % XP_PER_LEVEL,
        "xp_per_level": XP_PER_LEVEL,
        "daily_goal": daily_goal,
        "daily_goal_done": today_attempts,
        "daily_goal_progress": round(min(1.0, today_attempts / daily_goal), 3) if daily_goal else 0.0,
        "badges": badges,
        "badges_earned": sum(1 for b in badges if b["earned"]),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_gamification(), indent=2))

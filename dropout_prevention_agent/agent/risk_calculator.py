from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RiskInput:
    student_id: str
    current_gpa: float
    previous_gpa: float | None
    attendance_pct: float
    lms_last_active_days: int
    failed_modules_count: int = 0
    missed_assessments_count: int = 0
    course_load_credits: int = 0
    as_of: datetime | None = None


@dataclass(frozen=True)
class RiskResult:
    student_id: str
    score: int
    level: str
    reasons: list[dict[str, Any]]


def clamp_score(score: int) -> int:
    return max(0, min(100, score))


def risk_level(score: int) -> str:
    if score <= 30:
        return "LOW"
    if score <= 60:
        return "MEDIUM"
    return "HIGH"


def calculate_risk(inp: RiskInput) -> RiskResult:
    """Compute a deterministic risk score (no ML).

    Rules:
      - Attendance < 60% -> +30
      - GPA drop > 0.5 -> +25
      - LMS inactivity > 14 days -> +20
    - Failed/repeated modules >= 1 -> +15, >= 2 -> +25
    - Missed assessments >= 1 -> +10, >= 3 -> +20
    - Heavy course load credits >= 21 -> +10

    Returns:
      - score in [0, 100]
      - level in {LOW, MEDIUM, HIGH}
      - reasons: explainable breakdown of applied rules
    """

    score = 0
    reasons: list[dict[str, Any]] = []

    # Attendance rule
    if inp.attendance_pct < 60:
        score += 30
        reasons.append(
            {
                "rule": "attendance_lt_60",
                "points": 30,
                "evidence": {"attendance_pct": inp.attendance_pct},
                "explanation": "Attendance below 60%.",
            }
        )

    # GPA trend rule
    if inp.previous_gpa is not None:
        gpa_drop = inp.previous_gpa - inp.current_gpa
        if gpa_drop > 0.5:
            score += 25
            reasons.append(
                {
                    "rule": "gpa_drop_gt_0_5",
                    "points": 25,
                    "evidence": {
                        "previous_gpa": inp.previous_gpa,
                        "current_gpa": inp.current_gpa,
                        "gpa_drop": round(gpa_drop, 3),
                    },
                    "explanation": "GPA dropped by more than 0.5.",
                }
            )

    # LMS inactivity rule
    if inp.lms_last_active_days > 14:
        score += 20
        reasons.append(
            {
                "rule": "lms_inactive_gt_14_days",
                "points": 20,
                "evidence": {"lms_last_active_days": inp.lms_last_active_days},
                "explanation": "No LMS activity for more than 14 days.",
            }
        )

    # Failed/repeated modules rule
    failed = int(inp.failed_modules_count or 0)
    if failed >= 2:
        score += 25
        reasons.append(
            {
                "rule": "failed_modules_ge_2",
                "points": 25,
                "evidence": {"failed_modules_count": failed},
                "explanation": "Two or more failed/repeated modules.",
            }
        )
    elif failed >= 1:
        score += 15
        reasons.append(
            {
                "rule": "failed_modules_ge_1",
                "points": 15,
                "evidence": {"failed_modules_count": failed},
                "explanation": "At least one failed/repeated module.",
            }
        )

    # Missed assessments rule
    missed = int(inp.missed_assessments_count or 0)
    if missed >= 3:
        score += 20
        reasons.append(
            {
                "rule": "missed_assessments_ge_3",
                "points": 20,
                "evidence": {"missed_assessments_count": missed},
                "explanation": "Missed three or more assessments.",
            }
        )
    elif missed >= 1:
        score += 10
        reasons.append(
            {
                "rule": "missed_assessments_ge_1",
                "points": 10,
                "evidence": {"missed_assessments_count": missed},
                "explanation": "Missed at least one assessment.",
            }
        )

    # Course load rule
    credits = int(inp.course_load_credits or 0)
    if credits >= 21:
        score += 10
        reasons.append(
            {
                "rule": "course_load_credits_ge_21",
                "points": 10,
                "evidence": {"course_load_credits": credits},
                "explanation": "High course load (21+ credits).",
            }
        )

    score = clamp_score(score)

    return RiskResult(
        student_id=inp.student_id,
        score=score,
        level=risk_level(score),
        reasons=reasons,
    )

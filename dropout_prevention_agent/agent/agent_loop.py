from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from agent.decision_agent import DecisionAgent
from agent.memory_store import MemoryStore
from agent.risk_calculator import RiskInput, calculate_risk


@dataclass
class AgentRunResult:
    processed: int
    outputs_path: Path


def run_agent(
    *,
    students_csv: Path,
    decision_agent: DecisionAgent,
    memory: MemoryStore,
    outputs_path: Path,
    as_of: datetime | None = None,
    use_db_signals: bool = False,
) -> AgentRunResult:
    as_of = as_of or datetime.utcnow()

    if use_db_signals:
        rows = memory.list_latest_signals(limit=5000)
        df = pd.DataFrame(rows)
        if df.empty:
            raise ValueError("No student signals found in database. Use Data Entry or import CSV first.")
    else:
        df = pd.read_csv(students_csv)

    all_out: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        student_id = str(row["student_id"])
        memory.upsert_student(
            student_id,
            full_name=str(row.get("full_name", "")) or None,
            major=str(row.get("major", "")) or None,
            year_level=int(row.get("year_level")) if not pd.isna(row.get("year_level")) else None,
        )

        inp = RiskInput(
            student_id=student_id,
            current_gpa=float(row["current_gpa"]),
            previous_gpa=None if pd.isna(row.get("previous_gpa")) else float(row.get("previous_gpa")),
            attendance_pct=float(row["attendance_pct"]),
            lms_last_active_days=int(row["lms_last_active_days"]),
            failed_modules_count=int(0 if pd.isna(row.get("failed_modules_count")) else row.get("failed_modules_count")),
            missed_assessments_count=int(0 if pd.isna(row.get("missed_assessments_count")) else row.get("missed_assessments_count")),
            course_load_credits=int(0 if pd.isna(row.get("course_load_credits")) else row.get("course_load_credits")),
            as_of=as_of,
        )
        risk = calculate_risk(inp)
        memory.add_risk_snapshot(student_id, as_of, risk.score, risk.level, risk.reasons)

        context = {
            "student": {
                "student_id": student_id,
                "full_name": str(row.get("full_name", "")),
                "major": str(row.get("major", "")),
                "year_level": int(row.get("year_level")) if not pd.isna(row.get("year_level")) else None,
            },
            "signals": {
                "current_gpa": inp.current_gpa,
                "previous_gpa": inp.previous_gpa,
                "attendance_pct": inp.attendance_pct,
                "lms_last_active_days": inp.lms_last_active_days,
                "failed_modules_count": inp.failed_modules_count,
                "missed_assessments_count": inp.missed_assessments_count,
                "course_load_credits": inp.course_load_credits,
            },
            "risk": {
                "score": risk.score,
                "level": risk.level,
                "reasons": risk.reasons,
            },
            "constraints": {
                "no_punishment": True,
                "no_dropout_prediction": True,
                "no_diagnosis": True,
                "human_in_the_loop": True,
            },
        }

        rec = decision_agent.recommend(context)
        memory.add_recommendation(
            student_id=student_id,
            as_of=as_of,
            risk_score=risk.score,
            risk_level=risk.level,
            recommended_actions=rec["recommended_actions"],
            priority=rec["priority"],
            explanation=rec["explanation"],
            model_used=decision_agent.gemini.model if decision_agent.gemini.is_configured() else None,
        )

        all_out.append({"as_of": as_of.isoformat(), **context, "recommendation": rec})

    outputs_path.parent.mkdir(parents=True, exist_ok=True)
    outputs_path.write_text(json.dumps(all_out, ensure_ascii=False, indent=2), encoding="utf-8")

    logging.info("Processed %s students; wrote %s", len(all_out), outputs_path)
    return AgentRunResult(processed=len(all_out), outputs_path=outputs_path)

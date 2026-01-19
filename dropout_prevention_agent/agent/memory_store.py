from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from database.db_manager import DBManager


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


@dataclass
class MemoryStore:
    db: DBManager

    def _ensure_student_signals_schema(self) -> None:
        """Best-effort migration for existing SQLite DBs.

        `schema.sql` is applied via CREATE TABLE IF NOT EXISTS and won't add new columns
        to an existing table. This migrates `student_signals` by adding missing columns.
        """

        desired_cols: dict[str, str] = {
            "failed_modules_count": "INTEGER NOT NULL DEFAULT 0",
            "missed_assessments_count": "INTEGER NOT NULL DEFAULT 0",
            "course_load_credits": "INTEGER NOT NULL DEFAULT 0",
        }

        with self.db.connect() as conn:
            existing = {r["name"] for r in conn.execute("PRAGMA table_info(student_signals)").fetchall()}
            for col, ddl in desired_cols.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE student_signals ADD COLUMN {col} {ddl}")
            conn.commit()

    def upsert_student(self, student_id: str, full_name: str | None = None, major: str | None = None, year_level: int | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO students(student_id, full_name, major, year_level)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(student_id) DO UPDATE SET
                  full_name = COALESCE(excluded.full_name, students.full_name),
                  major = COALESCE(excluded.major, students.major),
                  year_level = COALESCE(excluded.year_level, students.year_level)
                """,
                (student_id, full_name, major, year_level),
            )
            conn.commit()

    def add_risk_snapshot(self, student_id: str, as_of: datetime, score: int, level: str, reasons: list[dict[str, Any]]) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO risk_snapshots(student_id, as_of, score, level, reasons_json)
                VALUES(?, ?, ?, ?, ?)
                """,
                (student_id, _iso(as_of), int(score), level, json.dumps(reasons, ensure_ascii=False)),
            )
            conn.commit()

    def add_recommendation(
        self,
        student_id: str,
        as_of: datetime,
        risk_score: int,
        risk_level: str,
        recommended_actions: list[dict[str, Any]],
        priority: str,
        explanation: str,
        model_used: str | None,
    ) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO recommendations(
                    student_id, as_of, risk_score, risk_level,
                    recommended_actions_json, priority, explanation, model_used
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    _iso(as_of),
                    int(risk_score),
                    risk_level,
                    json.dumps(recommended_actions, ensure_ascii=False),
                    priority,
                    explanation,
                    model_used,
                ),
            )
            conn.commit()

    def list_latest_risks(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT rs.student_id, s.full_name, rs.as_of, rs.score, rs.level
                FROM risk_snapshots rs
                JOIN students s ON s.student_id = rs.student_id
                WHERE rs.id IN (
                  SELECT MAX(id) FROM risk_snapshots GROUP BY student_id
                )
                ORDER BY rs.score DESC, rs.as_of DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_student_timeline(self, student_id: str) -> dict[str, list[dict[str, Any]]]:
        with self.db.connect() as conn:
            risks = conn.execute(
                """
                SELECT id, as_of, score, level, reasons_json
                FROM risk_snapshots
                WHERE student_id = ?
                ORDER BY as_of ASC
                """,
                (student_id,),
            ).fetchall()

            recs = conn.execute(
                """
                SELECT id, as_of, risk_score, risk_level, recommended_actions_json, priority, explanation, model_used
                FROM recommendations
                WHERE student_id = ?
                ORDER BY as_of ASC
                """,
                (student_id,),
            ).fetchall()

            interventions = conn.execute(
                """
                SELECT id, as_of, intervention_type, notes, status, outcome
                FROM interventions
                WHERE student_id = ?
                ORDER BY as_of ASC
                """,
                (student_id,),
            ).fetchall()

        def _decode(rows: list[Any], json_fields: set[str]) -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                for f in json_fields:
                    if f in d and d[f] is not None:
                        d[f] = json.loads(d[f])
                out.append(d)
            return out

        return {
            "risks": _decode(risks, {"reasons_json"}),
            "recommendations": _decode(recs, {"recommended_actions_json"}),
            "interventions": [dict(r) for r in interventions],
        }

    def add_intervention(self, student_id: str, as_of: datetime, intervention_type: str, notes: str | None, status: str = "proposed", outcome: str | None = None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO interventions(student_id, as_of, intervention_type, notes, status, outcome)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (student_id, _iso(as_of), intervention_type, notes, status, outcome),
            )
            conn.commit()

    def add_student_signals(
        self,
        *,
        student_id: str,
        as_of: datetime,
        current_gpa: float,
        previous_gpa: float | None,
        attendance_pct: float,
        lms_last_active_days: int,
        failed_modules_count: int,
        missed_assessments_count: int,
        course_load_credits: int,
        source: str = "manual_entry",
    ) -> None:
        self._ensure_student_signals_schema()
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO student_signals(
                    student_id, as_of,
                    current_gpa, previous_gpa, attendance_pct,
                    lms_last_active_days,
                    failed_modules_count, missed_assessments_count, course_load_credits,
                    source
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    _iso(as_of),
                    float(current_gpa),
                    None if previous_gpa is None else float(previous_gpa),
                    float(attendance_pct),
                    int(lms_last_active_days),
                    int(failed_modules_count),
                    int(missed_assessments_count),
                    int(course_load_credits),
                    source,
                ),
            )
            conn.commit()

    def get_latest_student_signals(self, student_id: str) -> dict[str, Any] | None:
        self._ensure_student_signals_schema()
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT id, student_id, as_of,
                       current_gpa, previous_gpa, attendance_pct,
                       lms_last_active_days,
                       failed_modules_count, missed_assessments_count, course_load_credits,
                       source
                FROM student_signals
                WHERE student_id = ?
                ORDER BY as_of DESC, id DESC
                LIMIT 1
                """,
                (student_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_latest_signals(self, limit: int = 500) -> list[dict[str, Any]]:
        self._ensure_student_signals_schema()
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT ss.student_id, s.full_name, ss.as_of,
                       ss.current_gpa, ss.previous_gpa, ss.attendance_pct,
                       ss.lms_last_active_days,
                       ss.failed_modules_count, ss.missed_assessments_count, ss.course_load_credits,
                       ss.source
                FROM student_signals ss
                JOIN students s ON s.student_id = ss.student_id
                WHERE ss.id IN (
                  SELECT MAX(id) FROM student_signals GROUP BY student_id
                )
                ORDER BY ss.as_of DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

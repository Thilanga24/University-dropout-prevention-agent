from __future__ import annotations

import sys
from pathlib import Path

from datetime import datetime
from datetime import timedelta

import pandas as pd
import streamlit as st


# Streamlit Cloud runs this file with a different working directory.
# Ensure the project root (parent of `dashboard/`) is on sys.path so
# imports like `from config.settings import settings` work reliably.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import settings
from database.db_manager import DBManager
from agent.memory_store import MemoryStore
from gemini.gemini_client import GeminiClient
from agent.decision_agent import DecisionAgent
from agent.agent_loop import run_agent
from dashboard.ui_helpers import df_to_csv_download, kpi_card, risk_badge, risk_color
from dashboard.reporting import build_student_html_report
from agent.risk_calculator import RiskInput, calculate_risk


st.set_page_config(page_title="Dropout Prevention Advisor Dashboard", layout="wide")

st.markdown(
        """
        <style>
            .block-container { padding-top: 1.25rem; }
            div[data-testid="stMetric"] { border: 1px solid rgba(0,0,0,0.08); padding: 14px; border-radius: 12px; }
            .muted { opacity: 0.78; font-size: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
)


def _init_memory() -> MemoryStore:
    dbm = DBManager(settings.database_path)
    dbm.init_db(schema_path=settings.database_path.parent / "database" / "schema.sql")
    return MemoryStore(dbm)


@st.cache_resource
def _cached_memory() -> MemoryStore:
    return _init_memory()


memory = _cached_memory()

st.title("University Dropout Prevention — Advisor Dashboard")
st.markdown(
    "<div class='muted'>Advisory-only • Human-in-the-loop decisions • No diagnosis • No punishment</div>",
    unsafe_allow_html=True,
)

latest = memory.list_latest_risks(limit=500)

# Top-level navigation
page = st.tabs(["Dashboard", "Data Entry"])

with st.sidebar:
    st.header("Filters")
    query = st.text_input("Search (name or ID)", value="")
    level_filter = st.multiselect("Risk level", ["HIGH", "MEDIUM", "LOW"], default=["HIGH", "MEDIUM", "LOW"])
    min_score = st.slider("Minimum score", min_value=0, max_value=100, value=0, step=5)
    st.divider()
    st.caption("Tip: use Refresh pipeline to rebuild snapshots.")

    st.subheader("Pipeline")
    confirm = st.checkbox("I confirm I want to refresh (writes DB)", value=False)
    if st.button("Refresh pipeline now", use_container_width=True, disabled=not confirm):
        with st.spinner("Running agent pipeline..."):
            gemini = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
            decision_agent = DecisionAgent(gemini)
            out_path = settings.outputs_dir / "recommendations.json"
            use_db = True
            try:
                use_db = len(memory.list_latest_signals(limit=1)) > 0
            except Exception:
                use_db = False
            run_agent(
                students_csv=settings.students_csv_path,
                decision_agent=decision_agent,
                memory=memory,
                outputs_path=out_path,
                use_db_signals=use_db,
            )
        st.success("Pipeline complete. Reloading data...")
        st.rerun()


with page[1]:
    st.header("Data Entry")
    st.caption("Enter latest signals for a student, calculate risk, and optionally store snapshot + recommendation.")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Student")
        de_student_id = st.text_input("Student ID", value="S005")
        de_full_name = st.text_input("Full name", value="")
        de_major = st.text_input("Major", value="")
        de_year = st.number_input("Year level", min_value=1, max_value=8, value=1, step=1)

    with right:
        st.subheader("Signals")
        de_current_gpa = st.number_input("Current GPA", min_value=0.0, max_value=4.0, value=3.0, step=0.1)
        de_previous_gpa = st.number_input("Previous GPA (optional)", min_value=0.0, max_value=4.0, value=3.0, step=0.1)
        prev_unknown = st.checkbox("Previous GPA unknown", value=False)
        de_attendance = st.number_input("Attendance %", min_value=0.0, max_value=100.0, value=80.0, step=1.0)
        de_lms_days = st.number_input("LMS inactivity (days)", min_value=0, max_value=365, value=3, step=1)
        st.caption("Academic progress")
        de_failed_modules = st.number_input("Failed modules / repeated courses", min_value=0, max_value=50, value=0, step=1)
        de_missed_assessments = st.number_input("Missed assessment count", min_value=0, max_value=50, value=0, step=1)
        de_course_load = st.number_input("Course load (credits)", min_value=0, max_value=60, value=0, step=1)

    st.divider()

    calc_col, save_col, rec_col = st.columns([1, 1, 1])
    calculate_now = calc_col.button("Calculate risk now", use_container_width=True)
    save_snapshot = save_col.checkbox("Save risk snapshot", value=True)
    save_recommendation = rec_col.checkbox("Also save recommendation", value=True)

    if calculate_now:
        if not de_student_id.strip():
            st.error("Student ID is required")
        else:
            as_of = datetime.utcnow()
            memory.upsert_student(
                de_student_id.strip(),
                full_name=de_full_name.strip() or None,
                major=de_major.strip() or None,
                year_level=int(de_year) if de_year else None,
            )

            prev_gpa_val = None if prev_unknown else float(de_previous_gpa)
            memory.add_student_signals(
                student_id=de_student_id.strip(),
                as_of=as_of,
                current_gpa=float(de_current_gpa),
                previous_gpa=prev_gpa_val,
                attendance_pct=float(de_attendance),
                lms_last_active_days=int(de_lms_days),
                failed_modules_count=int(de_failed_modules),
                missed_assessments_count=int(de_missed_assessments),
                course_load_credits=int(de_course_load),
                source="manual_entry",
            )

            risk_inp = RiskInput(
                student_id=de_student_id.strip(),
                current_gpa=float(de_current_gpa),
                previous_gpa=prev_gpa_val,
                attendance_pct=float(de_attendance),
                lms_last_active_days=int(de_lms_days),
                failed_modules_count=int(de_failed_modules),
                missed_assessments_count=int(de_missed_assessments),
                course_load_credits=int(de_course_load),
                as_of=as_of,
            )
            risk = calculate_risk(risk_inp)

            st.subheader("Result")
            r1, r2, r3 = st.columns([1, 1, 2])
            r1.metric("Risk score", risk.score)
            r2.metric("Risk level", risk.level)
            with r3:
                st.json(risk.reasons)

            if save_snapshot:
                memory.add_risk_snapshot(de_student_id.strip(), as_of, risk.score, risk.level, risk.reasons)

            if save_recommendation:
                gemini = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
                decision_agent = DecisionAgent(gemini)
                context = {
                    "student": {
                        "student_id": de_student_id.strip(),
                        "full_name": de_full_name.strip(),
                        "major": de_major.strip(),
                        "year_level": int(de_year),
                    },
                    "signals": {
                        "current_gpa": float(de_current_gpa),
                        "previous_gpa": prev_gpa_val,
                        "attendance_pct": float(de_attendance),
                        "lms_last_active_days": int(de_lms_days),
                        "failed_modules_count": int(de_failed_modules),
                        "missed_assessments_count": int(de_missed_assessments),
                        "course_load_credits": int(de_course_load),
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
                    student_id=de_student_id.strip(),
                    as_of=as_of,
                    risk_score=risk.score,
                    risk_level=risk.level,
                    recommended_actions=rec["recommended_actions"],
                    priority=rec["priority"],
                    explanation=rec["explanation"],
                    model_used=decision_agent.gemini.model if decision_agent.gemini.is_configured() else None,
                )

                st.success("Saved snapshot + recommendation.")
            else:
                st.success("Saved signals (and snapshot if enabled).")

            st.caption("Switch back to the Dashboard tab to see the student in the list.")


with page[0]:

    def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        # Always apply the risk-level filter.
        # If the user deselects all levels, show zero rows (not all rows).
        out = out[out["level"].isin(level_filter)]
        out = out[out["score"] >= min_score]
        if query.strip():
            q = query.strip()
            out = out[
                out["student_id"].astype(str).str.contains(q, case=False, na=False, regex=False)
                | out["full_name"].astype(str).str.contains(q, case=False, na=False, regex=False)
            ]
        return out

    if not latest:
        st.warning("No risk snapshots yet.")
        st.caption(
            "On Streamlit Cloud the database starts empty. Use the sidebar ‘Refresh pipeline now’ "
            "to generate snapshots from `data/students.csv`, or use the Data Entry tab."
        )

        # Show a safe preview so the app isn't "empty" on first deploy.
        try:
            seed = pd.read_csv(settings.students_csv_path)
            preview_rows: list[dict[str, object]] = []
            for _, row in seed.iterrows():
                inp = RiskInput(
                    student_id=str(row["student_id"]),
                    current_gpa=float(row["current_gpa"]),
                    previous_gpa=None if pd.isna(row.get("previous_gpa")) else float(row.get("previous_gpa")),
                    attendance_pct=float(row["attendance_pct"]),
                    lms_last_active_days=int(row["lms_last_active_days"]),
                    failed_modules_count=int(0 if pd.isna(row.get("failed_modules_count")) else row.get("failed_modules_count")),
                    missed_assessments_count=int(0 if pd.isna(row.get("missed_assessments_count")) else row.get("missed_assessments_count")),
                    course_load_credits=int(0 if pd.isna(row.get("course_load_credits")) else row.get("course_load_credits")),
                )
                risk = calculate_risk(inp)
                preview_rows.append(
                    {
                        "student_id": inp.student_id,
                        "full_name": str(row.get("full_name", "")),
                        "score": risk.score,
                        "level": risk.level,
                        "reasons": risk.reasons,
                    }
                )

            st.subheader("Preview (from data/students.csv)")
            df_preview = pd.DataFrame(preview_rows)
            df_preview["risk"] = df_preview["level"].apply(risk_badge)
            st.dataframe(
                df_preview[["student_id", "full_name", "score", "level", "risk"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%d"),
                },
            )

            if st.button("Generate snapshots now (writes DB)", use_container_width=True):
                with st.spinner("Running agent pipeline..."):
                    gemini = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
                    decision_agent = DecisionAgent(gemini)
                    out_path = settings.outputs_dir / "recommendations.json"
                    run_agent(
                        students_csv=settings.students_csv_path,
                        decision_agent=decision_agent,
                        memory=memory,
                        outputs_path=out_path,
                        use_db_signals=False,
                    )
                st.success("Snapshots generated. Reloading...")
                st.rerun()
        except Exception as e:
            st.info("Could not load demo data from `data/students.csv`. Add it to the repo or use Data Entry.")
            st.caption(f"Details: {e}")

        st.stop()

    df_all = pd.DataFrame(latest)
    df_all["risk"] = df_all["level"].apply(risk_badge)

# Add a derived date column for aggregation
df_all["as_of_dt"] = pd.to_datetime(df_all["as_of"], errors="coerce")
df_all["as_of_date"] = df_all["as_of_dt"].dt.date

# KPI row
high_count = int((df_all["level"] == "HIGH").sum())
med_count = int((df_all["level"] == "MEDIUM").sum())
low_count = int((df_all["level"] == "LOW").sum())

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Students monitored", len(df_all))
with k2:
    kpi_card("High risk", high_count)
with k3:
    kpi_card("Medium risk", med_count)
with k4:
    kpi_card("Low risk", low_count)

st.divider()

# Overview charts
ch1, ch2 = st.columns([1.2, 1])
with ch1:
    st.subheader("Risk distribution")
    dist = (
        df_all.groupby("level")["student_id"].count()
        .reindex(["HIGH", "MEDIUM", "LOW"])  # keep order
        .fillna(0)
        .astype(int)
    )
    dist_df = dist.reset_index().rename(columns={"student_id": "count"})
    st.bar_chart(dist_df.set_index("level")["count"], height=220)

with ch2:
    st.subheader("Snapshot trend")
    lookback_days = st.slider("Days", 7, 90, 30, step=1)
    cutoff = (datetime.utcnow() - timedelta(days=int(lookback_days))).date()
    trend = df_all[df_all["as_of_date"] >= cutoff].groupby(["as_of_date", "level"]).size().reset_index(name="count")
    if not trend.empty:
        pivot = trend.pivot(index="as_of_date", columns="level", values="count").fillna(0)
        # ensure columns order
        for c in ["HIGH", "MEDIUM", "LOW"]:
            if c not in pivot.columns:
                pivot[c] = 0
        pivot = pivot[["HIGH", "MEDIUM", "LOW"]]
        st.area_chart(pivot, height=220)
    else:
        st.caption("Not enough historical runs yet to show a trend.")

colA, colB = st.columns([1.6, 1])

with colA:
    st.subheader("Student list")
    df_view = _apply_filters(df_all)
    df_view = df_view.sort_values(["score", "as_of"], ascending=[False, False])
    df_to_show = df_view[["student_id", "full_name", "as_of", "score", "level", "risk"]].copy()

    st.dataframe(
        df_to_show,
        width="stretch",
        hide_index=True,
        column_config={
            "score": st.column_config.ProgressColumn("Risk score", min_value=0, max_value=100, format="%d"),
            "risk": st.column_config.TextColumn("Risk", help="Rule-based level"),
            "as_of": st.column_config.DatetimeColumn("As of"),
        },
    )
    df_to_csv_download(df_view, "Download filtered CSV", "filtered_risks.csv")

    # Quick selection
    st.markdown("**Select a student to view details**")
    selected_student_id = st.selectbox(
        "Student",
        options=df_view["student_id"].astype(str).tolist(),
        index=0 if len(df_view) else None,
        label_visibility="collapsed",
    )

with colB:
    st.subheader("Student profile")
    student_id = selected_student_id
    tl = memory.get_student_timeline(student_id)

    tab_risk, tab_recs, tab_int = st.tabs(["Risk", "Recommendations", "Interventions"])


    # Build helpful context from latest snapshot row
    latest_row = None
    try:
        latest_row = df_all[df_all["student_id"].astype(str) == str(student_id)].iloc[0].to_dict()
    except Exception:
        latest_row = None

    with tab_risk:
        risks = pd.DataFrame(tl["risks"])
        if not risks.empty:
            risks["as_of"] = pd.to_datetime(risks["as_of"], errors="coerce")
            st.markdown(
                f"**{student_id}**  •  Latest: **{int(risks.iloc[-1]['score'])}**  ({risks.iloc[-1]['level']})"
            )
            st.line_chart(risks.set_index("as_of")["score"], height=220)
            with st.expander("Explainability (rule triggers)"):
                st.json(risks.iloc[-1].get("reasons_json", []))
        else:
            st.warning("No risk history found for this student.")

    with tab_recs:
        recs = pd.DataFrame(tl["recommendations"])
        if not recs.empty:
            latest_rec = recs.iloc[-1].to_dict()
            priority = str(latest_rec.get("priority", "LOW"))
            st.markdown(
                f"<div style='padding:12px;border-radius:12px;border:1px solid rgba(255,255,255,0.08);background:#0b1220'>"
                f"<div class='muted'>Latest recommendation</div>"
                f"<div style='font-size:18px;font-weight:700;color:{risk_color(priority)}'>Priority: {priority}</div>"
                f"<div style='margin-top:8px'>{latest_rec.get('explanation','')}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

            st.markdown("**Recommended actions**")
            actions = latest_rec.get("recommended_actions_json", [])
            if isinstance(actions, list) and actions:
                for a in actions:
                    st.write(f"- **{a.get('type','')}** ({a.get('owner','')}) — {a.get('rationale','')}")
            else:
                st.caption("No actions available.")

            st.divider()
            st.subheader("Export")
            html_report = build_student_html_report(student_id=str(student_id), latest_row=latest_row, timeline=tl)
            st.download_button(
                "Download HTML report",
                data=html_report.encode("utf-8"),
                file_name=f"student_report_{student_id}.html",
                mime="text/html",
                use_container_width=True,
            )
            st.caption("PDF export can be added later if you want (needs extra dependencies).")
        else:
            st.info("No recommendations found yet. Run the pipeline.")

    with tab_int:
        st.markdown("**One‑click interventions**")
        b1, b2, b3 = st.columns(3)
        now = datetime.utcnow()
        if b1.button("Schedule advising (48h)", use_container_width=True):
            memory.add_intervention(
                student_id=str(student_id).strip(),
                as_of=now,
                intervention_type="Academic advising session",
                notes="Scheduled/initiated advisor outreach within 48 hours.",
                status="proposed",
            )
            st.success("Logged: Academic advising session")
        if b2.button("Refer tutoring", use_container_width=True):
            memory.add_intervention(
                student_id=str(student_id).strip(),
                as_of=now,
                intervention_type="Tutoring referral",
                notes="Shared tutoring options and initiated referral.",
                status="proposed",
            )
            st.success("Logged: Tutoring referral")
        if b3.button("Refer financial aid", use_container_width=True):
            memory.add_intervention(
                student_id=str(student_id).strip(),
                as_of=now,
                intervention_type="Financial aid referral",
                notes="Referred student to financial aid office / payment plan support.",
                status="proposed",
            )
            st.success("Logged: Financial aid referral")

        st.divider()
        st.subheader("Log intervention (human decision)")
        with st.form("intervention_form", clear_on_submit=True):
            intervention_type = st.selectbox(
                "Intervention type",
                [
                    "Academic advising session",
                    "Tutoring referral",
                    "Study plan coaching",
                    "Financial aid referral",
                    "Fee payment plan guidance",
                    "Wellbeing resources (non-diagnostic)",
                    "Time management resources",
                ],
            )
            status = st.selectbox("Status", ["proposed", "in_progress", "completed"])
            notes = st.text_area("Notes", placeholder="What was decided? Any constraints/next steps?")
            outcome = st.text_input("Outcome (optional)")
            submitted = st.form_submit_button("Save intervention")

        if submitted:
            memory.add_intervention(
                student_id=str(student_id).strip(),
                as_of=datetime.utcnow(),
                intervention_type=intervention_type,
                notes=notes.strip() or None,
                status=status,
                outcome=outcome.strip() or None,
            )
            st.success("Intervention saved")

        st.markdown("**Intervention history**")
        inv = pd.DataFrame(tl["interventions"])
        if not inv.empty:
            inv["as_of"] = pd.to_datetime(inv["as_of"], errors="coerce")
            st.dataframe(inv.sort_values("as_of", ascending=False), width="stretch", hide_index=True)
        else:
            st.caption("No interventions logged yet.")

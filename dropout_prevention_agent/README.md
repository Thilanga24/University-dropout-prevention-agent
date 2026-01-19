# University Dropout Prevention AI Agent (Rule-Based + Gemini)

An autonomous, **non-punitive** advisory agent that monitors student signals (grades, attendance, LMS activity, fee status), computes a **rule-based** risk score (no ML), and asks **Gemini** for ethically constrained intervention suggestions.

## Key rules (no ML)
- Attendance < 60% → +30
- GPA drop > 0.5 (vs previous term) → +25
- LMS inactivity > 14 days → +20
- Fee delay > 30 days → +25

Risk levels:
- 0–30 LOW
- 31–60 MEDIUM
- 61–100 HIGH

## Modules
- `agent/risk_calculator.py`: deterministic scoring + explanations
- `gemini/gemini_client.py`: Gemini API wrapper (safe, optional)
- `agent/decision_agent.py`: ethical prompt + structured recommendations
- `database/`: SQLite schema + manager
- `agent/memory_store.py`: persists risk & intervention history
- `agent/agent_loop.py`: batch process students
- `dashboard/app.py`: Streamlit advisor dashboard (human-in-the-loop)

## Quick start (Windows / cmd)
1) Create a virtual environment, install deps.
2) Copy `.env.example` → `.env` and set `GEMINI_API_KEY` (optional).
3) Run the pipeline or open dashboard.

## Notes
- This system **does not diagnose** mental health or predict dropout.
- Recommendations are **advisory only** and require a human decision.

from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def _esc(s: object) -> str:
    return html.escape("" if s is None else str(s))


def build_student_html_report(
    *,
    student_id: str,
    latest_row: dict[str, Any] | None,
    timeline: dict[str, list[dict[str, Any]]],
) -> str:
    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    name = _esc((latest_row or {}).get("full_name", ""))
    major = _esc((latest_row or {}).get("major", ""))

    def _li(text: str) -> str:
        return f"<li>{text}</li>"

    risks = timeline.get("risks", [])
    recs = timeline.get("recommendations", [])
    interventions = timeline.get("interventions", [])

    latest_risk = risks[-1] if risks else {}
    latest_rec = recs[-1] if recs else {}

    actions = latest_rec.get("recommended_actions_json", [])
    actions_html = "".join(
        _li(
            f"<b>{_esc(a.get('type'))}</b> ({_esc(a.get('owner'))}) — {_esc(a.get('rationale'))}"
        )
        for a in actions
    )

    inv_html = "".join(
        _li(
            f"{_esc(i.get('as_of'))}: <b>{_esc(i.get('intervention_type'))}</b> ({_esc(i.get('status'))}) — {_esc(i.get('notes'))}"
        )
        for i in reversed(interventions)
    )

    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <title>Student Support Report — { _esc(student_id) }</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 28px; color: #111827; }}
    .card {{ border: 1px solid #E5E7EB; border-radius: 12px; padding: 16px; margin: 14px 0; }}
    h1 {{ margin: 0 0 6px 0; }}
    .muted {{ color: #6B7280; font-size: 0.95rem; }}
    ul {{ margin: 8px 0 0 22px; }}
    .pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; background: #EEF2FF; }}
  </style>
</head>
<body>
  <h1>Student Support Report</h1>
  <div class='muted'>Generated: { _esc(now) } • Advisory-only • Human-in-the-loop</div>

  <div class='card'>
    <div class='pill'>Student ID: <b>{ _esc(student_id) }</b></div>
    <div style='margin-top:10px'>Name: <b>{name}</b></div>
    <div>Major: <b>{major}</b></div>
  </div>

  <div class='card'>
    <h2 style='margin:0'>Latest rule-based risk</h2>
    <div>Score: <b>{ _esc(latest_risk.get('score')) }</b></div>
    <div>Level: <b>{ _esc(latest_risk.get('level')) }</b></div>
    <div class='muted' style='margin-top:8px'>Reasons stored in system logs / database for transparency.</div>
  </div>

  <div class='card'>
    <h2 style='margin:0'>Recommended actions</h2>
    <div class='muted'>Note: recommendations are supportive and non-punitive.</div>
    <ul>{actions_html or '<li>No recommendations found.</li>'}</ul>
    <div style='margin-top:10px'><b>Explanation:</b> {_esc(latest_rec.get('explanation', ''))}</div>
  </div>

  <div class='card'>
    <h2 style='margin:0'>Logged interventions</h2>
    <ul>{inv_html or '<li>No interventions logged yet.</li>'}</ul>
  </div>

  <div class='muted'>This report does not diagnose or predict outcomes. It supports human advisors in offering resources.</div>
</body>
</html>"""

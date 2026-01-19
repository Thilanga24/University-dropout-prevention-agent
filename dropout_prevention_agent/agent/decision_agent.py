from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gemini.gemini_client import GeminiClient, GeminiError


ETHICAL_SYSTEM_PROMPT = """
You are an advisory decision-support assistant for a University Dropout Prevention system.

Hard constraints:
- Do NOT predict dropout.
- Do NOT label a student (no 'dropout-prone', no permanent labels).
- Do NOT provide medical or mental health diagnoses.
- Do NOT recommend punitive actions.
- Recommendations must be supportive, ethical, and explainable.
- Output must be JSON ONLY and match the schema.

You will be given structured signals (GPA trend, attendance, LMS activity, failed modules/repeats, missed assessments, course load), a numeric rule-based risk score and reasons.
Your job: recommend non-punitive interventions and a priority level for a human advisor.

JSON schema:
{
  "priority": "LOW"|"MEDIUM"|"HIGH",
  "recommended_actions": [
     {"type": string, "owner": "advisor"|"student"|"admin", "rationale": string}
  ],
  "explanation": string
}
""".strip()


@dataclass
class DecisionAgent:
    gemini: GeminiClient

    def recommend(self, context: dict[str, Any]) -> dict[str, Any]:
        """Return a structured recommendation.

        If Gemini is not configured, provide a deterministic fallback based on risk level.
        """

        if not self.gemini.is_configured():
            return self._fallback(context)

        try:
            out = self.gemini.generate_json(ETHICAL_SYSTEM_PROMPT, context)
            return self._validate(out)  # defensive
        except GeminiError:
            return self._fallback(context)

    def _fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        level = (context.get("risk", {}) or {}).get("level") or "LOW"

        if level == "HIGH":
            priority = "HIGH"
            actions = [
                {
                    "type": "Schedule advisor check-in within 48 hours",
                    "owner": "advisor",
                    "rationale": "High rule-based risk score; human review recommended soon.",
                },
                {
                    "type": "Offer study plan and tutoring referral",
                    "owner": "advisor",
                    "rationale": "Support academic recovery without punishment.",
                },
                {
                    "type": "Review academic plan (failed modules, assessments, load)",
                    "owner": "advisor",
                    "rationale": "Target practical academic barriers indicated by the signals.",
                },
            ]
        elif level == "MEDIUM":
            priority = "MEDIUM"
            actions = [
                {
                    "type": "Advisor outreach email + optional meeting",
                    "owner": "advisor",
                    "rationale": "Moderate risk; early support can prevent escalation.",
                },
                {
                    "type": "Share time-management and study resources",
                    "owner": "student",
                    "rationale": "Encourage self-directed improvements.",
                },
            ]
        else:
            priority = "LOW"
            actions = [
                {
                    "type": "Send positive check-in + resources",
                    "owner": "advisor",
                    "rationale": "Low risk; keep supportive contact.",
                }
            ]

        return {
            "priority": priority,
            "recommended_actions": actions,
            "explanation": "Fallback recommendations used because Gemini is not configured or unavailable.",
        }

    def _validate(self, out: dict[str, Any]) -> dict[str, Any]:
        priority = out.get("priority")
        if priority not in {"LOW", "MEDIUM", "HIGH"}:
            raise GeminiError("Invalid priority")
        actions = out.get("recommended_actions")
        if not isinstance(actions, list) or not actions:
            raise GeminiError("recommended_actions must be a non-empty list")
        for a in actions:
            if not isinstance(a, dict):
                raise GeminiError("Action must be object")
            if "type" not in a or "owner" not in a or "rationale" not in a:
                raise GeminiError("Action missing required fields")
        explanation = out.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            raise GeminiError("explanation required")
        return {
            "priority": priority,
            "recommended_actions": actions,
            "explanation": explanation,
        }

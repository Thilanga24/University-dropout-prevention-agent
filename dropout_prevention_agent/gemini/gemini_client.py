from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


class GeminiError(RuntimeError):
    pass


@dataclass
class GeminiClient:
    api_key: str | None
    model: str

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def generate_json(self, system_prompt: str, user_payload: dict[str, Any], timeout_s: int = 30) -> dict[str, Any]:
        """Calls Gemini and attempts to return a JSON object.

        If api_key is missing, raises GeminiError.

        Note: This uses the Google Generative Language REST endpoint.
        """

        if not self.api_key:
            raise GeminiError("GEMINI_API_KEY not configured")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {"Content-Type": "application/json"}

        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": system_prompt},
                        {"text": "\n\nINPUT_JSON:\n" + json.dumps(user_payload, ensure_ascii=False)},
                        {"text": "\n\nReturn ONLY valid JSON (no markdown, no backticks)."},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.9,
                "maxOutputTokens": 800,
            },
        }

        resp = requests.post(url, params={"key": self.api_key}, headers=headers, json=body, timeout=timeout_s)
        if resp.status_code != 200:
            raise GeminiError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            raise GeminiError(f"Unexpected Gemini response shape: {e}")

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise GeminiError(f"Gemini did not return valid JSON: {e}. Raw: {text[:500]}")

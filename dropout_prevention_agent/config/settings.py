from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    database_path: Path = PROJECT_ROOT / "university_agent.db"

    students_csv_path: Path = PROJECT_ROOT / "data" / "students.csv"
    policies_path: Path = PROJECT_ROOT / "data" / "intervention_policies.json"

    outputs_dir: Path = PROJECT_ROOT / "outputs"
    logs_dir: Path = PROJECT_ROOT / "logs"


settings = Settings()

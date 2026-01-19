from __future__ import annotations

import logging
from pathlib import Path

from config.settings import settings
from database.db_manager import DBManager
from agent.memory_store import MemoryStore
from gemini.gemini_client import GeminiClient
from agent.decision_agent import DecisionAgent
from agent.agent_loop import run_agent


def setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "agent.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path, encoding="utf-8"), logging.StreamHandler()],
    )


def main() -> int:
    setup_logging(settings.logs_dir)

    dbm = DBManager(settings.database_path)
    dbm.init_db(schema_path=Path(__file__).resolve().parent / "database" / "schema.sql")

    memory = MemoryStore(dbm)
    gemini = GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)
    decision_agent = DecisionAgent(gemini)

    out_path = settings.outputs_dir / "recommendations.json"
    result = run_agent(
        students_csv=settings.students_csv_path,
        decision_agent=decision_agent,
        memory=memory,
        outputs_path=out_path,
    )

    logging.info("Done. Processed=%s", result.processed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

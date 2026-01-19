from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DBManager:
    db_path: Path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self, schema_path: Path) -> None:
        schema_sql = schema_path.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema_sql)
            conn.commit()

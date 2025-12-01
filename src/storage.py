
import aiosqlite
import json
from typing import Any, Dict

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS var_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    path TEXT NOT NULL,     -- caminho da variável no address space
    value REAL,
    extra TEXT              -- JSON serializado como string
);

CREATE TABLE IF NOT EXISTS event_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    severity INTEGER NOT NULL,
    category TEXT
);
"""

INSERT_VAR_SQL = """
INSERT INTO var_history (ts, path, value, extra) VALUES (?, ?, ?, ?);
"""

INSERT_EVENT_SQL = """
INSERT INTO event_history (ts, source, message, severity, category) VALUES (?, ?, ?, ?, ?);
"""

class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(CREATE_TABLES_SQL)
            await db.commit()

    async def add_var(self, ts: str, path: str, value: float | None, extra: Dict[str, Any] | None = None):
        extra_json = json.dumps(extra or {})  # <-- serialize para string
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(INSERT_VAR_SQL, (ts, path, value, extra_json))
            await db.commit()

    async def add_event(self, ts: str, source: str, message: str, severity: int, category: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(INSERT_EVENT_SQL, (ts, source, message, severity, category))
            await db.commit()

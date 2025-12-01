#!/usr/bin/env python3
# scripts/check_db.py
"""
Check SQLite persistence for SCGDI:
- var_history: latest variables
- event_history: latest events

Usage:
  poetry run python scripts/check_db.py
  poetry run python scripts/check_db.py --limit 20
  poetry run python scripts/check_db.py --since "2025-08-14T00:00:00"
  poetry run python scripts/check_db.py --watch 2
"""
from __future__ import annotations
import argparse
import os
import sqlite3
import time
from typing import Optional

from dotenv import load_dotenv

def get_db_path() -> str:
    load_dotenv()
    return os.getenv("DB_PATH", "./scgdi_history.sqlite")

def ensure_tables(conn: sqlite3.Connection) -> tuple[bool, bool]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r[0] for r in cur.fetchall()}
    return ("var_history" in names, "event_history" in names)

def print_vars(conn: sqlite3.Connection, limit: int, since: Optional[str]) -> None:
    q = """SELECT ts, path, value FROM var_history {} ORDER BY ts DESC LIMIT ?"""
    filt = f"WHERE ts >= '{since}'" if since else ""
    for row in conn.execute(q.format(filt), (limit,)):
        ts, path, value = row
        print(f"[VAR] {ts} | {path:<64} | {value}")

def print_events(conn: sqlite3.Connection, limit: int, since: Optional[str]) -> None:
    q = """SELECT ts, category, severity, message FROM event_history {} ORDER BY ts DESC LIMIT ?"""
    filt = f"WHERE ts >= '{since}'" if since else ""
    for row in conn.execute(q.format(filt), (limit,)):
        ts, cat, sev, msg = row
        print(f"[EVT] {ts} | {cat:<24} | sev={sev:<3} | {msg}")

def print_counts(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    v = cur.execute("SELECT count(*) FROM var_history").fetchone()[0]
    e = cur.execute("SELECT count(*) FROM event_history").fetchone()[0]
    print(f"\n[COUNT] var_history={v}  event_history={e}")
    print("[COUNT] by severity:")
    for sev, c in conn.execute("SELECT severity, count(*) FROM event_history GROUP BY severity ORDER BY severity"):
        print(f"  - {sev}: {c}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=str, default=None, help="Path to sqlite DB (default: from .env DB_PATH)")
    parser.add_argument("--limit", type=int, default=15, help="Rows to show from each table")
    parser.add_argument("--since", type=str, default=None, help="Filter ts >= ISO (e.g., 2025-08-14T00:00:00)")
    parser.add_argument("--watch", type=int, default=0, help="Repeat every N seconds")
    args = parser.parse_args()

    db_path = args.db or get_db_path()
    conn = sqlite3.connect(db_path)

    try:
        has_vars, has_evts = ensure_tables(conn)
        if not has_vars and not has_evts:
            print(f"[ERR] No var_history/event_history in {db_path}. Is the server writing to this DB?")
            return 2

        def run_once():
            os.system("clear")
            print(f"[DB] {db_path}")
            print("=" * 80)
            if has_vars:
                print_vars(conn, args.limit, args.since)
            if has_evts:
                print()
                print_events(conn, args.limit, args.since)
            print_counts(conn)

        if args.watch > 0:
            while True:
                run_once()
                time.sleep(args.watch)
        else:
            run_once()
    finally:
        conn.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

import json
import os
import sqlite3
import time
from typing import Any
from uuid import uuid4


def get_default_db_path(base_dir: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    return os.path.join(base_dir, "local.db")


def ensure_user_id(session_state: dict) -> str:
    uid = session_state.get("user_id")
    if isinstance(uid, str) and uid.strip():
        return uid
    uid = str(uuid4())
    session_state["user_id"] = uid
    return uid


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db(db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkins (
              user_id TEXT NOT NULL,
              spot_id TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              PRIMARY KEY (user_id, spot_id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
              trip_id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              name TEXT NOT NULL,
              city TEXT NOT NULL,
              route TEXT NOT NULL,
              created_at INTEGER NOT NULL,
              data_json TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_trips_user_created ON trips(user_id, created_at);")
    finally:
        conn.close()


def has_checkin(db_path: str, user_id: str, spot_id: str) -> bool:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM checkins WHERE user_id = ? AND spot_id = ? LIMIT 1;",
            (user_id, spot_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def insert_checkin(db_path: str, user_id: str, spot_id: str) -> bool:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO checkins(user_id, spot_id, created_at) VALUES(?, ?, ?);",
            (user_id, spot_id, int(time.time())),
        )
        return cur.rowcount == 1
    finally:
        conn.close()


def count_checkins(db_path: str, user_id: str, spot_id: str) -> int:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(1) FROM checkins WHERE user_id = ? AND spot_id = ?;",
            (user_id, spot_id),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def list_checkins(db_path: str, user_id: str, limit: int = 1000) -> list[str]:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT spot_id FROM checkins WHERE user_id = ? ORDER BY created_at DESC LIMIT ?;",
            (user_id, int(limit)),
        ).fetchall()
        return [str(r[0]) for r in rows]
    finally:
        conn.close()


def save_trip(db_path: str, user_id: str, trip: dict[str, Any]) -> str:
    init_db(db_path)
    trip_id = str(uuid4())
    name = str(trip.get("name") or "")
    city = str(trip.get("city") or "")
    route = str(trip.get("route") or "")
    payload = json.dumps(trip, ensure_ascii=False)
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO trips(trip_id, user_id, name, city, route, created_at, data_json) VALUES(?, ?, ?, ?, ?, ?, ?);",
            (trip_id, user_id, name, city, route, int(time.time()), payload),
        )
    finally:
        conn.close()
    return trip_id


def update_trip(db_path: str, user_id: str, trip_id: str, trip: dict[str, Any]) -> bool:
    init_db(db_path)
    name = str(trip.get("name") or "")
    city = str(trip.get("city") or "")
    route = str(trip.get("route") or "")
    payload = json.dumps(trip, ensure_ascii=False)
    conn = _connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE trips SET name = ?, city = ?, route = ?, data_json = ? WHERE user_id = ? AND trip_id = ?;",
            (name, city, route, payload, user_id, trip_id),
        )
        return cur.rowcount == 1
    finally:
        conn.close()


def delete_trip(db_path: str, user_id: str, trip_id: str) -> None:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        conn.execute(
            "DELETE FROM trips WHERE user_id = ? AND trip_id = ?;",
            (user_id, trip_id),
        )
    finally:
        conn.close()


def list_trips(db_path: str, user_id: str, limit: int = 30) -> list[dict[str, Any]]:
    init_db(db_path)
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT trip_id, data_json FROM trips WHERE user_id = ? ORDER BY created_at DESC LIMIT ?;",
            (user_id, int(limit)),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for trip_id, data_json in rows:
            try:
                item = json.loads(data_json)
            except Exception:
                item = {}
            if isinstance(item, dict):
                item["id"] = trip_id
                out.append(item)
        return out
    finally:
        conn.close()

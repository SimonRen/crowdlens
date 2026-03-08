import sqlite3
import uuid
from datetime import datetime, timezone


def upsert_channel(conn: sqlite3.Connection, channel_id: str, filename: str, label: str):
    conn.execute(
        "INSERT OR REPLACE INTO channels (id, filename, label) VALUES (?, ?, ?)",
        (channel_id, filename, label),
    )
    conn.commit()


def list_channels(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM channels").fetchall()
    return [dict(r) for r in rows]


def create_session(conn: sqlite3.Connection, channel_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO sessions (id, channel_id, started_at, status) VALUES (?, ?, ?, 'active')",
        (session_id, channel_id, now),
    )
    conn.commit()
    return session_id


def stop_session(conn: sqlite3.Connection, session_id: str):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE sessions SET stopped_at = ?, status = 'stopped' WHERE id = ?",
        (now, session_id),
    )
    conn.commit()


def list_active_sessions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM sessions WHERE status = 'active'").fetchall()
    return [dict(r) for r in rows]


def list_sessions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM sessions ORDER BY started_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_session(conn: sqlite3.Connection, session_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return dict(row) if row else None


def upsert_track(conn: sqlite3.Connection, session_id: str, track_id: int,
                 classification: str | None, age_estimate: float | None,
                 gender_estimate: str | None, confidence: float | None):
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO tracks (id, session_id, track_id, classification, age_estimate,
                            gender_estimate, confidence, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id, track_id) DO UPDATE SET
            classification = COALESCE(excluded.classification, classification),
            age_estimate = COALESCE(excluded.age_estimate, age_estimate),
            gender_estimate = COALESCE(excluded.gender_estimate, gender_estimate),
            confidence = COALESCE(excluded.confidence, confidence),
            last_seen_at = excluded.last_seen_at
    """, (row_id, session_id, track_id, classification, age_estimate,
          gender_estimate, confidence, now, now))
    # NOTE: caller is responsible for conn.commit() (batched per frame)


def get_session_tracks(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute("SELECT * FROM tracks WHERE session_id = ?", (session_id,)).fetchall()
    return [dict(r) for r in rows]


def insert_snapshot(conn: sqlite3.Connection, session_id: str, **counts):
    snap_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO session_snapshots (id, session_id, timestamp,
            men_in_frame, women_in_frame, children_in_frame, unknown_in_frame,
            total_unique_men, total_unique_women, total_unique_children, total_unique_unknown)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (snap_id, session_id, now,
          counts.get("men_in_frame", 0), counts.get("women_in_frame", 0),
          counts.get("children_in_frame", 0), counts.get("unknown_in_frame", 0),
          counts.get("total_unique_men", 0), counts.get("total_unique_women", 0),
          counts.get("total_unique_children", 0), counts.get("total_unique_unknown", 0)))
    conn.commit()


def get_session_snapshots(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM session_snapshots WHERE session_id = ? ORDER BY timestamp",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_session_stats(conn: sqlite3.Connection, session_id: str) -> dict:
    """Get summary stats for a session: track counts by classification + snapshots."""
    tracks = get_session_tracks(conn, session_id)
    summary = {"men": 0, "women": 0, "children": 0, "unknown": 0, "total": len(tracks)}
    for t in tracks:
        cls = t.get("classification", "unknown") or "unknown"
        if cls == "man":
            summary["men"] += 1
        elif cls == "woman":
            summary["women"] += 1
        elif cls == "child":
            summary["children"] += 1
        else:
            summary["unknown"] += 1

    snapshots = get_session_snapshots(conn, session_id)
    return {"summary": summary, "snapshots": snapshots}

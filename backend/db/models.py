import sqlite3


def create_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id          TEXT PRIMARY KEY,
            filename    TEXT NOT NULL,
            label       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            channel_id  TEXT NOT NULL REFERENCES channels(id),
            started_at  TEXT NOT NULL,
            stopped_at  TEXT,
            status      TEXT NOT NULL DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS tracks (
            id              TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL REFERENCES sessions(id),
            track_id        INTEGER NOT NULL,
            classification  TEXT,
            age_estimate    REAL,
            gender_estimate TEXT,
            confidence      REAL,
            first_seen_at   TEXT NOT NULL,
            last_seen_at    TEXT NOT NULL,
            UNIQUE(session_id, track_id)
        );

        CREATE TABLE IF NOT EXISTS session_snapshots (
            id                      TEXT PRIMARY KEY,
            session_id              TEXT NOT NULL REFERENCES sessions(id),
            timestamp               TEXT NOT NULL,
            men_in_frame            INTEGER NOT NULL DEFAULT 0,
            women_in_frame          INTEGER NOT NULL DEFAULT 0,
            children_in_frame       INTEGER NOT NULL DEFAULT 0,
            unknown_in_frame        INTEGER NOT NULL DEFAULT 0,
            total_unique_men        INTEGER NOT NULL DEFAULT 0,
            total_unique_women      INTEGER NOT NULL DEFAULT 0,
            total_unique_children   INTEGER NOT NULL DEFAULT 0,
            total_unique_unknown    INTEGER NOT NULL DEFAULT 0
        );
    """)
    conn.commit()

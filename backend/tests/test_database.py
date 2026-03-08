import os
import tempfile
import pytest
from db.database import init_db, get_connection
from db.models import create_tables
from db import queries


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def db(db_path):
    conn = init_db(db_path)
    create_tables(conn)
    return conn


def test_create_tables(db):
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "channels" in tables
    assert "sessions" in tables
    assert "tracks" in tables
    assert "session_snapshots" in tables


def test_insert_and_query_channel(db):
    queries.upsert_channel(db, "test-ch", "test.mp4", "Test Channel")
    channels = queries.list_channels(db)
    assert len(channels) == 1
    assert channels[0]["id"] == "test-ch"


def test_session_lifecycle(db):
    queries.upsert_channel(db, "ch1", "vid.mp4", "Channel 1")
    session_id = queries.create_session(db, "ch1")
    assert session_id is not None

    sessions = queries.list_sessions(db)
    assert len(sessions) == 1
    assert sessions[0]["status"] == "active"

    queries.stop_session(db, session_id)
    sessions = queries.list_sessions(db)
    assert sessions[0]["status"] == "stopped"
    assert sessions[0]["stopped_at"] is not None


def test_track_upsert(db):
    queries.upsert_channel(db, "ch1", "vid.mp4", "Channel 1")
    sid = queries.create_session(db, "ch1")

    queries.upsert_track(db, sid, track_id=1, classification="man",
                         age_estimate=30.0, gender_estimate="male", confidence=0.95)
    queries.upsert_track(db, sid, track_id=1, classification="man",
                         age_estimate=30.0, gender_estimate="male", confidence=0.95)

    tracks = queries.get_session_tracks(db, sid)
    assert len(tracks) == 1  # upsert, not duplicate


def test_snapshot_insert_and_query(db):
    queries.upsert_channel(db, "ch1", "vid.mp4", "Channel 1")
    sid = queries.create_session(db, "ch1")

    queries.insert_snapshot(db, sid, men_in_frame=3, women_in_frame=2,
                            children_in_frame=1, unknown_in_frame=0,
                            total_unique_men=5, total_unique_women=4,
                            total_unique_children=2, total_unique_unknown=1)

    snapshots = queries.get_session_snapshots(db, sid)
    assert len(snapshots) == 1
    assert snapshots[0]["men_in_frame"] == 3

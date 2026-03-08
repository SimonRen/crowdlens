"""
Smoke test for the CrowdLens.
Requires: docker compose up running + at least one MP4 in ./videos/

Run: python tests/test_smoke.py
"""
import sys
import time
import httpx

BASE_URL = "http://localhost:3000"  # through nginx proxy


def test_health():
    r = httpx.get(f"{BASE_URL}/api/health", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["worker_alive"] is True
    print("✓ Health check passed")


def test_channels():
    r = httpx.get(f"{BASE_URL}/api/channels", timeout=10)
    assert r.status_code == 200
    channels = r.json()
    assert len(channels) > 0, "No channels found — add MP4 files to ./videos/"
    print(f"✓ Found {len(channels)} channel(s): {[c['id'] for c in channels]}")
    return channels


def test_session_lifecycle(channel_id: str):
    # Start session
    r = httpx.post(f"{BASE_URL}/api/sessions/start",
                   json={"channel_id": channel_id}, timeout=10)
    assert r.status_code == 200
    session_id = r.json()["session_id"]
    print(f"✓ Session started: {session_id}")

    # Wait for processing
    time.sleep(3)

    # Check MJPEG stream
    with httpx.stream("GET", f"{BASE_URL}/api/stream", timeout=10) as resp:
        assert resp.status_code == 200
        assert "multipart/x-mixed-replace" in resp.headers.get("content-type", "")
        # Read a few bytes to confirm data is flowing
        chunk = next(resp.iter_bytes(chunk_size=1024))
        assert len(chunk) > 0
    print("✓ MJPEG stream is active")

    # Check SSE stream
    with httpx.stream("GET", f"{BASE_URL}/api/events", timeout=10) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data:"):
                print("✓ SSE stats event received")
                break

    # Stop session
    r = httpx.post(f"{BASE_URL}/api/sessions/stop",
                   json={"session_id": session_id}, timeout=10)
    assert r.status_code == 200
    print("✓ Session stopped")

    # Check session appears in history
    r = httpx.get(f"{BASE_URL}/api/sessions", timeout=10)
    sessions = r.json()
    assert any(s["id"] == session_id for s in sessions)
    print("✓ Session appears in history")

    # Check session stats
    r = httpx.get(f"{BASE_URL}/api/sessions/{session_id}/stats", timeout=10)
    assert r.status_code == 200
    stats = r.json()
    print(f"✓ Session stats: {stats['summary']}")


def main():
    print("=== CrowdLens Smoke Test ===\n")
    try:
        test_health()
        channels = test_channels()
        test_session_lifecycle(channels[0]["id"])
        print("\n=== ALL SMOKE TESTS PASSED ===")
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

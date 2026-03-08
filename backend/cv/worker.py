import multiprocessing as mp
import queue
import signal
import time
from collections import Counter
from datetime import datetime, timezone

import cv2
import numpy as np
import supervision as sv

from config import Settings
from cv.detector import PersonDetector
from cv.classifier import PersonClassifier
from cv.annotator import FrameAnnotator
from db.database import init_db
from db.models import create_tables
from db import queries


def put_drop_oldest(q: mp.Queue, item):
    """Put item into bounded queue, dropping oldest if full."""
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            pass


def cv_worker(
    frame_queue: mp.Queue,
    stats_queue: mp.Queue,
    cmd_queue: mp.Queue,
    stop_event: mp.Event,
    settings_dict: dict,
):
    """Main CV worker process. Runs detection + tracking + classification loop."""
    # Reset signal handlers (safety for spawn)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    settings = Settings(**settings_dict)

    # Initialize components
    detector = PersonDetector(
        model_name=f"{settings.detection_model}.pt",
        input_size=settings.input_resolution,
    )
    classifier = PersonClassifier()
    annotator = FrameAnnotator()

    # Initialize DB (own connection for this process)
    conn = init_db(settings.database_path)
    create_tables(conn)

    # State
    cap = None
    session_id = None
    frame_count = 0
    classifications: dict[int, dict] = {}  # track_id -> best classification
    vote_history: dict[int, list[str]] = {}  # track_id -> list of classification votes
    last_snapshot_time = 0.0
    fps_counter = 0
    fps_time = time.time()
    current_fps = 0.0

    try:
        while not stop_event.is_set():
            # Check for commands
            try:
                cmd = cmd_queue.get_nowait()
                if cmd["type"] == "start":
                    channel = cmd["channel"]
                    video_path = f"{settings.videos_dir}/{channel['filename']}"
                    cap = cv2.VideoCapture(video_path)
                    session_id = cmd["session_id"]
                    frame_count = 0
                    classifications.clear()
                    vote_history.clear()
                    last_snapshot_time = time.time()
                    detector.reset_tracker()
                elif cmd["type"] == "stop":
                    if cap is not None:
                        cap.release()
                        cap = None
                    session_id = None
                    classifications.clear()
                    vote_history.clear()
            except queue.Empty:
                pass

            # If no active session, sleep briefly and continue
            if cap is None or session_id is None:
                time.sleep(0.05)
                continue

            ret, frame = cap.read()
            if not ret:
                # Loop the video — reset tracker and classifications to avoid
                # double-counting the same people across loops
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                detector.reset_tracker()
                classifications.clear()
                vote_history.clear()
                continue

            frame_count += 1

            # FPS tracking
            fps_counter += 1
            elapsed = time.time() - fps_time
            if elapsed >= 1.0:
                current_fps = fps_counter / elapsed
                fps_counter = 0
                fps_time = time.time()

            # 1. Detect + track
            det = detector.detect_and_track(frame)
            track_ids = det["track_ids"]
            boxes = det["boxes_xyxy"]

            # 2. Classify with CLIP + majority voting
            # Classify on interval frames OR when a new track_id is first seen
            run_classification = frame_count % settings.classification_interval == 0
            for tid, box in zip(track_ids, boxes):
                is_new = tid not in classifications
                if not run_classification and not is_new:
                    continue

                x1, y1, x2, y2 = box.astype(int)
                crop = frame[y1:y2, x1:x2]
                result = classifier.classify_crop(crop)

                if result is not None:
                    cls_label = result["classification"]

                    # Accumulate votes (keep last 5)
                    if tid not in vote_history:
                        vote_history[tid] = []
                    vote_history[tid].append(cls_label)
                    if len(vote_history[tid]) > 5:
                        vote_history[tid] = vote_history[tid][-5:]

                    # Use majority vote as final classification
                    majority = Counter(vote_history[tid]).most_common(1)[0][0]
                    classifications[tid] = {
                        "classification": majority,
                        "confidence": result["confidence"],
                    }

                    queries.upsert_track(
                        conn, session_id, tid,
                        classification=majority,
                        age_estimate=None,
                        gender_estimate=None,
                        confidence=result["confidence"],
                    )
                elif tid not in classifications:
                    classifications[tid] = {
                        "classification": "unknown",
                        "confidence": None,
                    }
                    queries.upsert_track(
                        conn, session_id, tid,
                        classification="unknown",
                        age_estimate=None,
                        gender_estimate=None,
                        confidence=None,
                    )

            # 3. Annotate frame
            detections = sv.Detections.from_ultralytics(det["result"])
            annotated = annotator.annotate(frame, detections, classifications)

            # 4. Encode JPEG and push to frame queue
            _, jpeg = cv2.imencode(".jpg", annotated,
                                    [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])
            put_drop_oldest(frame_queue, jpeg.tobytes())

            # 5. Compute current stats and push
            in_frame = {"men": 0, "women": 0, "children": 0, "unknown": 0}
            for tid in track_ids:
                cls = classifications.get(tid, {}).get("classification", "unknown")
                if cls == "man":
                    in_frame["men"] += 1
                elif cls == "woman":
                    in_frame["women"] += 1
                elif cls == "child":
                    in_frame["children"] += 1
                else:
                    in_frame["unknown"] += 1

            # Session totals from in-memory classifications (no per-frame DB query)
            session_total = {"men": 0, "women": 0, "children": 0, "unknown": 0}
            for cls_info in classifications.values():
                c = cls_info.get("classification", "unknown")
                if c == "man":
                    session_total["men"] += 1
                elif c == "woman":
                    session_total["women"] += 1
                elif c == "child":
                    session_total["children"] += 1
                else:
                    session_total["unknown"] += 1

            stats = {
                "in_frame": in_frame,
                "session_total": session_total,
                "fps": round(current_fps, 1),
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            put_drop_oldest(stats_queue, stats)

            # 6. Periodic snapshot
            now = time.time()
            if now - last_snapshot_time >= settings.snapshot_interval:
                queries.insert_snapshot(
                    conn, session_id,
                    men_in_frame=in_frame["men"],
                    women_in_frame=in_frame["women"],
                    children_in_frame=in_frame["children"],
                    unknown_in_frame=in_frame["unknown"],
                    total_unique_men=session_total["men"],
                    total_unique_women=session_total["women"],
                    total_unique_children=session_total["children"],
                    total_unique_unknown=session_total["unknown"],
                )
                last_snapshot_time = now

    finally:
        if cap is not None:
            cap.release()
        conn.close()

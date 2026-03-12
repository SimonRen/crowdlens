import base64 as b64
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

# Number of consistent votes before a track is considered stable
STABLE_VOTE_COUNT = 5


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


def _is_stable(votes: list[str]) -> bool:
    """Check if a track's vote history has a stable majority."""
    if len(votes) < STABLE_VOTE_COUNT:
        return False
    majority, count = Counter(votes).most_common(1)[0]
    return count >= STABLE_VOTE_COUNT


def cv_worker(
    frame_queue: mp.Queue,
    stats_queue: mp.Queue,
    cmd_queue: mp.Queue,
    match_queue: mp.Queue,
    stop_event: mp.Event,
    settings_dict: dict,
):
    """Main CV worker process. Runs detection + tracking + classification loop."""
    # Reset signal handlers (safety for spawn)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    settings = Settings(**settings_dict)

    # Initialize components
    device = settings.resolve_device()
    detector = PersonDetector(
        model_name=f"{settings.detection_model}.pt",
        input_size=settings.input_resolution,
        device=device,
    )
    classifier = PersonClassifier(
        child_age_threshold=settings.child_age_threshold,
        gender_confidence_threshold=settings.gender_confidence_threshold,
        min_crop_height=settings.min_crop_height,
        device=device,
    )
    annotator = FrameAnnotator()

    # Initialize DB (own connection for this process)
    conn = init_db(settings.database_path)
    create_tables(conn)

    # State
    cap = None
    session_id = None
    frame_count = 0
    frame_interval = 1.0 / settings.max_fps
    next_frame_time = 0.0
    classifications: dict[int, dict] = {}  # track_id -> best classification
    vote_history: dict[int, list[str]] = {}  # track_id -> list of classification votes
    last_snapshot_time = 0.0
    fps_counter = 0
    fps_time = time.time()
    current_fps = 0.0

    # Target search state
    target_embedding = None  # np.ndarray or None
    match_threshold = settings.match_threshold
    match_paused = False
    frozen_frame_jpeg = None  # JPEG bytes to re-push during MATCH_PAUSED
    face_matcher = None  # lazy-loaded

    try:
        while not stop_event.is_set():
            # Check for commands
            try:
                cmd = cmd_queue.get_nowait()
                if cmd["type"] == "start":
                    channel = cmd["channel"]
                    video_path = f"{settings.videos_dir}/{channel['filename']}"
                    cap = cv2.VideoCapture(video_path)
                    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    target_fps = min(video_fps, settings.max_fps)
                    frame_interval = 1.0 / target_fps
                    next_frame_time = time.time()
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
                    match_paused = False
                    frozen_frame_jpeg = None
                    classifications.clear()
                    vote_history.clear()
                elif cmd["type"] == "set_target":
                    target_embedding = np.array(cmd["embedding"], dtype=np.float32)
                    match_threshold = cmd["threshold"]
                    match_paused = False
                    if face_matcher is None:
                        from cv.face_matcher import FaceMatcher
                        face_matcher = FaceMatcher(
                            model_name=settings.face_model_name,
                            device=device,
                        )
                elif cmd["type"] == "clear_target":
                    target_embedding = None
                    match_paused = False
                    frozen_frame_jpeg = None
                elif cmd["type"] == "update_threshold":
                    match_threshold = cmd["threshold"]
                elif cmd["type"] == "resume":
                    match_paused = False
                    frozen_frame_jpeg = None
            except queue.Empty:
                pass

            # If no active session, sleep briefly and continue
            if cap is None or session_id is None:
                time.sleep(0.05)
                continue

            # MATCH_PAUSED: re-push frozen frame, check for resume
            if match_paused:
                if frozen_frame_jpeg is not None:
                    put_drop_oldest(frame_queue, frozen_frame_jpeg)
                time.sleep(frame_interval)
                continue

            # Frame pacing — wait until next frame time for stable playback
            now = time.time()
            sleep_dur = next_frame_time - now
            if sleep_dur > 0:
                time.sleep(sleep_dur)
            next_frame_time = time.time() + frame_interval

            ret, frame = cap.read()
            if not ret:
                # Loop the video — reset tracker and classifications to avoid
                # double-counting the same people across loops
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                detector.reset_tracker()
                classifications.clear()
                vote_history.clear()
                next_frame_time = time.time()
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

            # 2. Classify with MiVOLO V2 (batched) + majority voting
            # Classify on interval frames OR when a new track_id is first seen
            # Skip tracks with stable vote history (early exit)
            run_classification = frame_count % settings.classification_interval == 0
            crops_to_classify: list[np.ndarray] = []
            tids_to_classify: list[int] = []

            for tid, box in zip(track_ids, boxes):
                is_new = tid not in classifications
                is_stable = not is_new and _is_stable(vote_history.get(tid, []))
                if not is_new and (not run_classification or is_stable):
                    continue

                x1, y1, x2, y2 = box.astype(int)
                crop = frame[y1:y2, x1:x2]
                crops_to_classify.append(crop)
                tids_to_classify.append(tid)

            # Batched inference
            db_dirty = False
            if crops_to_classify:
                batch_results = classifier.classify_batch(crops_to_classify)
                for tid, result in zip(tids_to_classify, batch_results):
                    if result is not None:
                        cls_label = result["classification"]

                        # Accumulate votes (keep last window)
                        if tid not in vote_history:
                            vote_history[tid] = []
                        vote_history[tid].append(cls_label)
                        if len(vote_history[tid]) > STABLE_VOTE_COUNT:
                            vote_history[tid] = vote_history[tid][-STABLE_VOTE_COUNT:]

                        # Use majority vote as final classification
                        majority = Counter(vote_history[tid]).most_common(1)[0][0]
                        classifications[tid] = {
                            "classification": majority,
                            "confidence": result["confidence"],
                            "age": result.get("age"),
                        }

                        queries.upsert_track(
                            conn, session_id, tid,
                            classification=majority,
                            age_estimate=result.get("age"),
                            gender_estimate=result["classification"],
                            confidence=result["confidence"],
                        )
                        db_dirty = True
                    elif tid not in classifications:
                        classifications[tid] = {
                            "classification": "unknown",
                            "confidence": None,
                            "age": None,
                        }
                        queries.upsert_track(
                            conn, session_id, tid,
                            classification="unknown",
                            age_estimate=None,
                            gender_estimate=None,
                            confidence=None,
                        )
                        db_dirty = True

            # Batch commit once per frame instead of per-track
            if db_dirty:
                conn.commit()

            # 3. Annotate frame
            detections = sv.Detections.from_ultralytics(det["result"])
            annotated = annotator.annotate(frame, detections, classifications)

            # Face matching (on same interval as classification)
            matched_tid = None
            matched_box = None
            if target_embedding is not None and face_matcher is not None and run_classification:
                for tid, box in zip(track_ids, boxes):
                    x1, y1, x2, y2 = box.astype(int)
                    crop = frame[y1:y2, x1:x2]
                    if crop.shape[0] < settings.min_crop_height or crop.shape[1] < 20:
                        continue
                    emb = face_matcher.extract_embedding(crop)
                    if emb is None:
                        continue
                    similarity = face_matcher.compare(emb, target_embedding)
                    if similarity >= match_threshold:
                        matched_tid = tid
                        matched_box = box.astype(int)
                        # Override classification for annotation
                        classifications[tid] = {
                            "classification": "match",
                            "similarity": similarity,
                            "confidence": similarity,
                            "age": classifications.get(tid, {}).get("age"),
                        }
                        # Re-annotate with match highlight
                        annotated = annotator.annotate(frame, detections, classifications)
                        break  # first match wins

            # 4. Encode JPEG and push to frame queue
            _, jpeg = cv2.imencode(".jpg", annotated,
                                    [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])
            put_drop_oldest(frame_queue, jpeg.tobytes())

            # If match found, send match event and enter MATCH_PAUSED
            if matched_tid is not None:
                x1, y1, x2, y2 = matched_box
                crop_bgr = frame[y1:y2, x1:x2]
                _, crop_jpg = cv2.imencode(".jpg", crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])

                match_event = {
                    "type": "match",
                    "track_id": matched_tid,
                    "similarity": round(classifications[matched_tid]["similarity"], 4),
                    "frame_jpeg": b64.b64encode(jpeg.tobytes()).decode("ascii"),
                    "crop_jpeg": b64.b64encode(crop_jpg.tobytes()).decode("ascii"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                put_drop_oldest(match_queue, match_event)

                frozen_frame_jpeg = jpeg.tobytes()
                match_paused = True
                continue  # skip stats push, enter pause on next iteration

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

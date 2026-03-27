from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from traffic_analyzer.models.schemas import Comment, GPSPoint
from traffic_analyzer.utils.time import parse_ts_to_epoch_ms

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SessionData:
    session_id: str
    points: list[GPSPoint]
    comments: list[Comment]
    meta: dict[str, Any]


POINT_ALIASES = {
    "ts": ["ts", "timestamp", "time", "t", "client_timestamp_ms", "timestamp_ms"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "lng", "longitude"],
    "accuracy_m": ["accuracy_m", "accuracy", "acc"],
    "speed_mps": ["speed_mps", "speed", "velocity", "speed_ms"],
    "heading_deg": ["heading_deg", "heading", "course", "bearing"],
}


def _pick(raw: dict[str, Any], key: str, default: Any = None) -> Any:
    for alias in POINT_ALIASES[key]:
        if alias in raw and raw[alias] is not None:
            return raw[alias]
    return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _read_points_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _resolve_session_file(root: Path, meta: dict[str, Any], preferred_meta_key: str, fallback_name: str) -> Path:
    # device-export format stores canonical filenames in meta.json
    rel = meta.get(preferred_meta_key)
    if isinstance(rel, str) and rel.strip():
        candidate = root / rel.strip()
        if candidate.exists():
            return candidate
    return root / fallback_name


def _iter_session_dirs(sessions_dir: Path) -> list[Path]:
    # Support both flat layout:
    #   sessions/<session_id>/meta.json
    # and nested date layout:
    #   sessions/YYYY-MM-DD/<session_id>/meta.json
    session_dirs = {meta.parent for meta in sessions_dir.rglob("meta.json")}
    return sorted(session_dirs)


def load_sessions(sessions_dir: Path) -> list[SessionData]:
    sessions: list[SessionData] = []
    for root in _iter_session_dirs(sessions_dir):
        meta_path = root / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        session_id = str(meta.get("session_id") or root.name)

        points_jsonl_path = _resolve_session_file(root, meta, "points_file_jsonl", "points.jsonl")
        points_csv_path = _resolve_session_file(root, meta, "points_file_csv", "points.csv")

        raw_points: list[dict[str, Any]]
        if points_jsonl_path.exists():
            raw_points = _read_jsonl(points_jsonl_path)
        elif points_csv_path.exists():
            raw_points = _read_points_csv(points_csv_path)
        else:
            logger.warning("Skipping invalid session dir (no points): %s", root)
            continue

        points: list[GPSPoint] = []
        for rp in raw_points:
            try:
                points.append(
                    GPSPoint(
                        session_id=session_id,
                        ts=parse_ts_to_epoch_ms(_pick(rp, "ts")),
                        lat=float(_pick(rp, "lat")),
                        lon=float(_pick(rp, "lon")),
                        accuracy_m=float(_pick(rp, "accuracy_m", 20.0)),
                        speed_mps=float(_pick(rp, "speed_mps", 0.0) or 0.0),
                        heading_deg=float(_pick(rp, "heading_deg", 0.0) or 0.0),
                        source_speed="device" if _pick(rp, "speed_mps") is not None else "derived",
                        source_heading="device" if _pick(rp, "heading_deg") is not None else "derived",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Bad point in %s: %s", root, exc)

        comments: list[Comment] = []
        comments_path = _resolve_session_file(root, meta, "sensor_events_file_jsonl", "comments.jsonl")
        if comments_path.exists():
            try:
                for i, rc in enumerate(_read_jsonl(comments_path)):
                    comments.append(
                        Comment(
                            comment_id=f"{session_id}_c_{i}",
                            session_id=session_id,
                            ts=parse_ts_to_epoch_ms(rc.get("ts") or rc.get("timestamp") or rc.get("client_timestamp_ms")),
                            lat=float(rc.get("lat") or rc.get("latitude")),
                            lon=float(rc.get("lon") or rc.get("lng") or rc.get("longitude")),
                            text=str(rc.get("text") or rc.get("comment") or ""),
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("comments.jsonl invalid in %s: %s", root, exc)
        sessions.append(SessionData(session_id=session_id, points=points, comments=comments, meta=meta))
    return sessions

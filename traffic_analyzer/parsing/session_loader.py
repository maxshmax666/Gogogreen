from __future__ import annotations

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
    "ts": ["ts", "timestamp", "time", "t"],
    "lat": ["lat", "latitude"],
    "lon": ["lon", "lng", "longitude"],
    "accuracy_m": ["accuracy_m", "accuracy", "acc"],
    "speed_mps": ["speed_mps", "speed", "velocity"],
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


def load_sessions(sessions_dir: Path) -> list[SessionData]:
    sessions: list[SessionData] = []
    for root in sorted(p for p in sessions_dir.iterdir() if p.is_dir()):
        meta_path = root / "meta.json"
        points_path = root / "points.jsonl"
        if not (meta_path.exists() and points_path.exists()):
            logger.warning("Skipping invalid session dir: %s", root)
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        session_id = str(meta.get("session_id") or root.name)
        raw_points = _read_jsonl(points_path)
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
                logger.warning("Bad point in %s: %s", points_path, exc)

        comments: list[Comment] = []
        comments_path = root / "comments.jsonl"
        if comments_path.exists():
            try:
                for i, rc in enumerate(_read_jsonl(comments_path)):
                    comments.append(
                        Comment(
                            comment_id=f"{session_id}_c_{i}",
                            session_id=session_id,
                            ts=parse_ts_to_epoch_ms(rc.get("ts") or rc.get("timestamp")),
                            lat=float(rc.get("lat")),
                            lon=float(rc.get("lon")),
                            text=str(rc.get("text") or rc.get("comment") or ""),
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("comments.jsonl invalid in %s: %s", root, exc)
        sessions.append(SessionData(session_id=session_id, points=points, comments=comments, meta=meta))
    return sessions

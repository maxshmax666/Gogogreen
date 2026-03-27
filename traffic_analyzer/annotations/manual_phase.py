from __future__ import annotations

import re
from statistics import pstdev

from traffic_analyzer.config import ParserConfig
from traffic_analyzer.models.schemas import Comment, ManualPhaseAnnotation, Observation
from traffic_analyzer.utils.geo import angular_distance_deg, haversine_m

PHASE_TOKENS = {
    "red": "red",
    "r": "red",
    "красный": "red",
    "красн": "red",
    "green": "green",
    "g": "green",
    "зеленый": "green",
    "зелёный": "green",
    "зел": "green",
    "yellow": "yellow",
    "y": "yellow",
    "желтый": "yellow",
    "жёлтый": "yellow",
}

_SIGNAL_HINTS = {
    "remaining": ["left", "остал", "remain", "через"],
    "duration": ["usually", "обычно", "duration", "длит"],
}


def parse_manual_phase_text(text: str) -> tuple[str, float | None, str, float]:
    norm = re.sub(r"\s+", " ", text.strip().lower())
    pattern = re.compile(r"(red|green|yellow|r|g|y|красн\w*|зелен\w*|зел\w*|ж[её]лт\w*)\s*[:= ]?\s*(\d{1,3})?")
    m = pattern.search(norm)
    if not m:
        return "unknown", None, "uncertain", 0.0
    token = m.group(1)
    phase = "unknown"
    for key, val in PHASE_TOKENS.items():
        if token.startswith(key):
            phase = val
            break
    sec = float(m.group(2)) if m.group(2) else None
    semantic = "uncertain"
    if sec is not None:
        semantic = "remaining_time"
    if any(h in norm for h in _SIGNAL_HINTS["duration"]):
        semantic = "phase_duration"
    conf = 0.9 if phase != "unknown" and sec is not None else 0.5
    return phase, sec, semantic, conf


def extract_manual_annotations(comments: list[Comment]) -> list[ManualPhaseAnnotation]:
    out: list[ManualPhaseAnnotation] = []
    for c in comments:
        phase, sec, semantic, conf = parse_manual_phase_text(c.text)
        if phase == "unknown":
            continue
        out.append(
            ManualPhaseAnnotation(
                annotation_id=f"ann_{c.comment_id}",
                session_id=c.session_id,
                ts=c.ts,
                lat=c.lat,
                lon=c.lon,
                heading_deg=0.0,
                raw_text=c.text,
                parsed_phase=phase,
                parsed_seconds=sec,
                semantic_type=semantic,
                confidence=conf,
            )
        )
    return out


def link_annotations(
    annotations: list[ManualPhaseAnnotation], observations: list[Observation], parser_cfg: ParserConfig
) -> None:
    for ann in annotations:
        best: tuple[Observation, float] | None = None
        for obs in observations:
            dt = abs(ann.ts - obs.ts) / 1000.0
            if dt > parser_cfg.max_comment_link_time_sec:
                continue
            d = haversine_m(ann.lat, ann.lon, obs.lat, obs.lon)
            if d > parser_cfg.max_comment_link_distance_m:
                continue
            h_score = angular_distance_deg(ann.heading_deg, obs.heading_deg) / 180
            score = dt + d / 10 + h_score
            if best is None or score < best[1]:
                best = (obs, score)
        if best is not None:
            ann.linked_observation_id = best[0].observation_id


def stable_annotation_stats(annotations: list[ManualPhaseAnnotation]) -> tuple[float | None, float]:
    vals = [a.parsed_seconds for a in annotations if a.parsed_seconds is not None]
    if len(vals) < 2:
        return None, 0.0
    std = pstdev(vals)
    return sum(vals) / len(vals), std

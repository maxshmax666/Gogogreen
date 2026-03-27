from __future__ import annotations

from statistics import median

from traffic_analyzer.config import EventConfig, ParserConfig
from traffic_analyzer.models.schemas import Comment, GPSPoint, Observation
from traffic_analyzer.utils.geo import haversine_m


def detect_observations(points: list[GPSPoint], cfg: EventConfig) -> list[Observation]:
    obs: list[Observation] = []
    if len(points) < 3:
        return obs
    start_ts = points[0].ts
    end_ts = points[-1].ts
    stopped = False
    stop_idx = -1
    oid = 0
    for i, p in enumerate(points):
        near_start = (p.ts - start_ts) / 1000.0 <= cfg.near_session_boundary_sec
        near_end = (end_ts - p.ts) / 1000.0 <= cfg.near_session_boundary_sec
        if not stopped and p.smoothed_speed_mps <= cfg.low_speed_mps:
            stopped = True
            stop_idx = i
            obs.append(
                Observation(
                    observation_id=f"obs_{oid}",
                    session_id=p.session_id,
                    event_type="stop_start",
                    ts=p.ts,
                    lat=p.lat,
                    lon=p.lon,
                    heading_deg=p.smoothed_heading_deg,
                    speed_mps=p.smoothed_speed_mps,
                    near_session_start=near_start,
                    near_session_end=near_end,
                    quality_weight=max(0.1, 1 - p.accuracy_m / 150),
                )
            )
            oid += 1
        elif stopped and p.smoothed_speed_mps >= cfg.move_speed_mps:
            stop_pt = points[stop_idx]
            stop_duration_sec = (p.ts - stop_pt.ts) / 1000.0
            event_type = "go_start"
            if stop_duration_sec < cfg.min_stop_duration_sec:
                event_type = "pass_through"
            elif stop_duration_sec > cfg.max_stop_duration_sec:
                event_type = "likely_non_signal_stop"
            obs.append(
                Observation(
                    observation_id=f"obs_{oid}",
                    session_id=p.session_id,
                    event_type=event_type,
                    ts=p.ts,
                    lat=p.lat,
                    lon=p.lon,
                    heading_deg=p.smoothed_heading_deg,
                    speed_mps=p.smoothed_speed_mps,
                    stop_duration_sec=stop_duration_sec,
                    near_session_start=near_start,
                    near_session_end=near_end,
                    quality_weight=max(0.1, 1 - median([stop_pt.accuracy_m, p.accuracy_m]) / 150),
                )
            )
            oid += 1
            stopped = False
            stop_idx = -1
    return obs


def link_comments(
    comments: list[Comment], observations: list[Observation], parser_cfg: ParserConfig
) -> dict[str, str]:
    links: dict[str, str] = {}
    for c in comments:
        best: tuple[str, float] | None = None
        for o in observations:
            dt = abs(c.ts - o.ts) / 1000.0
            if dt > parser_cfg.max_comment_link_time_sec:
                continue
            d = haversine_m(c.lat, c.lon, o.lat, o.lon)
            if d > parser_cfg.max_comment_link_distance_m:
                continue
            score = dt + d / 10.0
            if best is None or score < best[1]:
                best = (o.observation_id, score)
        if best:
            links[c.comment_id] = best[0]
            for o in observations:
                if o.observation_id == best[0]:
                    o.linked_comment_ids.append(c.comment_id)
                    break
    return links

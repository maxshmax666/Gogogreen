from __future__ import annotations

from collections import deque

from traffic_analyzer.config import NormalizationConfig
from traffic_analyzer.models.schemas import GPSPoint
from traffic_analyzer.utils.geo import bearing_deg, haversine_m


def normalize_points(points: list[GPSPoint], config: NormalizationConfig) -> list[GPSPoint]:
    if not points:
        return points
    points.sort(key=lambda p: p.ts)
    prev = None
    for i, p in enumerate(points):
        p.accuracy_m = min(max(p.accuracy_m, config.min_accuracy_m), config.max_accuracy_m)
        if prev is not None:
            dt = max((p.ts - prev.ts) / 1000.0, 0.001)
            d = haversine_m(prev.lat, prev.lon, p.lat, p.lon)
            derived_speed = d / dt
            if p.source_speed == "derived" or p.speed_mps <= 0:
                p.speed_mps = derived_speed
                p.source_speed = "derived"
            if p.source_heading == "derived" or p.heading_deg <= 0:
                p.heading_deg = bearing_deg(prev.lat, prev.lon, p.lat, p.lon)
                p.source_heading = "derived"
            if derived_speed > config.max_jump_mps and p.accuracy_m > 40:
                p.lat = prev.lat
                p.lon = prev.lon
                p.speed_mps = 0.0
        prev = p

    speed_window: deque[float] = deque(maxlen=config.smoothing_window)
    heading_window: deque[float] = deque(maxlen=config.smoothing_window)
    for p in points:
        speed_window.append(p.speed_mps)
        heading_window.append(p.heading_deg)
        p.smoothed_speed_mps = sum(speed_window) / len(speed_window)
        p.smoothed_heading_deg = sum(heading_window) / len(heading_window)
    return points

from __future__ import annotations

from traffic_analyzer.models.schemas import IntersectionModel
from traffic_analyzer.prediction.next_light import predict_next_light, prediction_to_dict
from traffic_analyzer.routing.interfaces import Route
from traffic_analyzer.config import GuidanceConfig


def predict_route(
    route: Route,
    intersections: list[IntersectionModel],
    timestamp_ms: int,
    guidance_cfg: GuidanceConfig,
) -> list[dict]:
    out = []
    if not route.points:
        return out
    for rp in route.points[:10]:
        pred = predict_next_light(
            intersections,
            lat=rp.lat,
            lon=rp.lon,
            heading_deg=0.0,
            speed_mps=10.0,
            timestamp_ms=timestamp_ms,
            guidance_cfg=guidance_cfg,
        )
        out.append(prediction_to_dict(pred))
    return out

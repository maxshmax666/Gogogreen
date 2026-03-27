from __future__ import annotations

from dataclasses import asdict
import math

from traffic_analyzer.config import GuidanceConfig
from traffic_analyzer.models.schemas import IntersectionModel, NextLightPrediction
from traffic_analyzer.utils.geo import angular_distance_deg, haversine_m


def predict_next_light(
    intersections: list[IntersectionModel],
    lat: float,
    lon: float,
    heading_deg: float,
    speed_mps: float,
    timestamp_ms: int,
    guidance_cfg: GuidanceConfig,
) -> NextLightPrediction:
    best = None
    for i in intersections:
        for a in i.approaches:
            if i.disabled:
                continue
            d = haversine_m(lat, lon, i.center_lat, i.center_lon)
            if d > 400:
                continue
            bucket_heading = (a.heading_bucket + 0.5) * 45
            hd = angular_distance_deg(heading_deg, bucket_heading)
            if hd > 90:
                continue
            score = d + hd * 2
            if best is None or score < best[0]:
                best = (score, i, a, d, hd)

    if best is None:
        return NextLightPrediction(
            next_light_id=None,
            approach_id=None,
            distance_m=None,
            eta_sec=None,
            predicted_phase_at_eta="unknown",
            time_to_phase_change_sec=None,
            recommendation="no_reliable_advice",
            target_speed_kmh=None,
            target_speed_range_kmh=None,
            confidence=0.0,
            confidence_breakdown={
                "map_match_confidence": 0.0,
                "next_light_selection_confidence": 0.0,
                "phase_prediction_confidence": 0.0,
                "eta_confidence": 0.0,
                "guidance_confidence": 0.0,
            },
            explanation="No plausible next light in forward direction.",
        )
    _, inter, app, dist, hd = best
    eta = dist / max(speed_mps, 1.0)
    map_c = max(0.1, 1 - dist / 400)
    sel_c = max(0.1, 1 - hd / 120)
    phase_c = app.confidence
    eta_c = 0.9 if speed_mps > 1 else 0.3
    conf = round(map_c * 0.2 + sel_c * 0.2 + phase_c * 0.4 + eta_c * 0.2, 3)

    predicted_phase = "unknown"
    time_to_change = None
    if app.estimated_cycle_sec and app.estimated_green_sec and app.estimated_red_sec:
        pos = (timestamp_ms / 1000) % app.estimated_cycle_sec
        if pos <= app.estimated_green_sec:
            predicted_phase = "green"
            time_to_change = app.estimated_green_sec - pos
        else:
            predicted_phase = "red"
            time_to_change = app.estimated_cycle_sec - pos

    rec = "no_reliable_advice"
    target = None
    target_range = None
    if conf > 0.5 and time_to_change is not None and eta < guidance_cfg.eta_horizon_sec:
        if predicted_phase == "red" and eta < time_to_change:
            rec = "slow_down"
            target = max(guidance_cfg.min_speed_kmh, speed_mps * 3.6 * 0.8)
        elif predicted_phase == "green" and eta > time_to_change:
            rec = "slight_accelerate"
            target = min(guidance_cfg.max_speed_kmh, speed_mps * 3.6 * 1.1)
        else:
            rec = "hold_speed"
            target = max(guidance_cfg.min_speed_kmh, min(guidance_cfg.max_speed_kmh, speed_mps * 3.6))
        target_range = (max(guidance_cfg.min_speed_kmh, target - 5), min(guidance_cfg.max_speed_kmh, target + 5))

    return NextLightPrediction(
        next_light_id=inter.intersection_id,
        approach_id=app.approach_id,
        distance_m=round(dist, 1),
        eta_sec=round(eta, 1),
        predicted_phase_at_eta=predicted_phase,
        time_to_phase_change_sec=round(time_to_change, 1) if time_to_change is not None else None,
        recommendation=rec,
        target_speed_kmh=round(target, 1) if target is not None else None,
        target_speed_range_kmh=(round(target_range[0], 1), round(target_range[1], 1)) if target_range else None,
        confidence=conf,
        confidence_breakdown={
            "map_match_confidence": round(map_c, 3),
            "next_light_selection_confidence": round(sel_c, 3),
            "phase_prediction_confidence": round(phase_c, 3),
            "eta_confidence": round(eta_c, 3),
            "guidance_confidence": conf,
        },
        explanation=f"Selected {inter.intersection_id}/{app.approach_id} by forward proximity and heading match.",
    )


def prediction_to_dict(pred: NextLightPrediction) -> dict:
    return asdict(pred)

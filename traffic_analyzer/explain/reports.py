from __future__ import annotations

from traffic_analyzer.models.schemas import IntersectionModel, ManualPhaseAnnotation


def explain_intersection(intersections: list[IntersectionModel], intersection_id: str) -> dict:
    for i in intersections:
        if i.intersection_id == intersection_id:
            return {
                "intersection_id": i.intersection_id,
                "center": {"lat": i.center_lat, "lon": i.center_lon},
                "disabled": i.disabled,
                "approaches": [
                    {
                        "approach_id": a.approach_id,
                        "regime_class": a.regime_class,
                        "confidence": a.confidence,
                        "samples": a.samples_total,
                        "source_breakdown": a.source_breakdown,
                        "conflicts": a.conflict_flags,
                        "estimated_cycle_sec": a.estimated_cycle_sec,
                    }
                    for a in i.approaches
                ],
            }
    return {"error": "intersection_not_found"}


def explain_approach(intersections: list[IntersectionModel], intersection_id: str, approach_id: str) -> dict:
    for i in intersections:
        if i.intersection_id != intersection_id:
            continue
        for a in i.approaches:
            if a.approach_id == approach_id:
                return {
                    "intersection_id": i.intersection_id,
                    "approach_id": a.approach_id,
                    "regime": a.regime_class,
                    "confidence": a.confidence,
                    "manual_annotation_count": a.manual_annotation_count,
                    "gps_observation_count": a.gps_observation_count,
                    "day_part_profiles": a.day_part_profiles,
                    "phase_offset": {
                        "value_sec": a.estimated_phase_offset_sec,
                        "confidence": a.estimated_phase_offset_confidence,
                    },
                    "conflict_flags": a.conflict_flags,
                }
    return {"error": "approach_not_found"}


def explain_annotation(annotations: list[ManualPhaseAnnotation], annotation_id: str) -> dict:
    for a in annotations:
        if a.annotation_id == annotation_id:
            return {
                "annotation_id": a.annotation_id,
                "raw_text": a.raw_text,
                "parsed_phase": a.parsed_phase,
                "parsed_seconds": a.parsed_seconds,
                "semantic_type": a.semantic_type,
                "linked_observation_id": a.linked_observation_id,
                "linked_intersection_id": a.linked_intersection_id,
                "linked_approach_id": a.linked_approach_id,
                "confidence": a.confidence,
            }
    return {"error": "annotation_not_found"}

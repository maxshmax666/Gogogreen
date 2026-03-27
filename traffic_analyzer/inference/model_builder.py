from __future__ import annotations

from collections import defaultdict
from statistics import median, pstdev

from traffic_analyzer.annotations.manual_phase import stable_annotation_stats
from traffic_analyzer.config import InferenceConfig
from traffic_analyzer.models.schemas import (
    ApproachModel,
    IntersectionModel,
    ManualPhaseAnnotation,
    Observation,
)
from traffic_analyzer.utils.time import day_part, slot_key


def _estimate_cycle(go_timestamps: list[int], min_samples: int) -> tuple[float | None, float]:
    if len(go_timestamps) < min_samples:
        return None, 0.0
    go_timestamps = sorted(go_timestamps)
    intervals = [(b - a) / 1000.0 for a, b in zip(go_timestamps, go_timestamps[1:]) if b > a]
    if len(intervals) < min_samples - 1:
        return None, 0.0
    c = median(intervals)
    std = pstdev(intervals) if len(intervals) > 1 else 0.0
    conf = max(0.1, min(0.95, 1 - std / max(c, 1)))
    return c, conf


def build_model(
    clustered: list[dict],
    annotations: list[ManualPhaseAnnotation],
    cfg: InferenceConfig,
) -> list[IntersectionModel]:
    ann_by_obs = defaultdict(list)
    for a in annotations:
        if a.linked_observation_id:
            ann_by_obs[a.linked_observation_id].append(a)

    intersections: list[IntersectionModel] = []
    for c in clustered:
        approaches: list[ApproachModel] = []
        for a in c["approaches"]:
            obs: list[Observation] = a["observations"]
            stops = [o for o in obs if o.event_type == "stop_start"]
            passes = [o for o in obs if o.event_type == "pass_through"]
            gos = [o for o in obs if o.event_type == "go_start"]
            stop_durs = [o.stop_duration_sec for o in gos if o.stop_duration_sec is not None]

            linked_annotations = []
            for o in obs:
                linked_annotations.extend(ann_by_obs.get(o.observation_id, []))
            manual_mean, manual_std = stable_annotation_stats(linked_annotations)

            cycle, cycle_conf = _estimate_cycle([o.ts for o in gos], cfg.min_samples_for_cycle)
            estimated_red = median(stop_durs) if stop_durs else None
            estimated_green = None
            if cycle and estimated_red:
                estimated_green = max(5.0, cycle - estimated_red)
            if manual_mean and any(x.parsed_phase == "red" for x in linked_annotations):
                estimated_red = manual_mean
                if estimated_green and cycle:
                    estimated_green = max(5.0, cycle - estimated_red)

            source_breakdown = {
                "manual": len(linked_annotations),
                "gps": len(obs),
                "comments": sum(len(o.linked_comment_ids) for o in obs),
            }
            conflict_flags: list[str] = []
            if manual_mean and estimated_red and abs(manual_mean - estimated_red) > 12:
                conflict_flags.append("manual_vs_gps_red_duration")

            confidence = min(
                0.99,
                0.1 + cycle_conf * 0.4 + min(len(obs) / 20, 0.25) + min(len(linked_annotations) / 10, 0.25),
            )
            regime = "sparse_observations"
            stability = 0.0
            if cycle and confidence > 0.7:
                regime = "probable_signalized"
            if manual_mean and manual_std <= cfg.stable_std_threshold_sec and len(linked_annotations) >= cfg.strong_manual_threshold:
                regime = "stable_fixed_cycle"
                stability = max(0.0, 1 - manual_std / max(manual_mean, 1))
                confidence = max(confidence, 0.85)

            slots: dict[str, dict[str, float | int | None]] = defaultdict(lambda: {"samples_total": 0, "stop_samples": 0})
            day_parts: dict[str, dict[str, float | int | None]] = defaultdict(lambda: {"samples_total": 0, "p_red": 0.0})
            for o in obs:
                sk = slot_key(o.ts, cfg.time_slot_minutes)
                dp = day_part(o.ts)
                slots[sk]["samples_total"] += 1
                day_parts[dp]["samples_total"] += 1
                if o.event_type in {"stop_start", "go_start"}:
                    slots[sk]["stop_samples"] += 1
                    day_parts[dp]["p_red"] += 1
            for dp, stats in day_parts.items():
                total = stats["samples_total"] or 1
                stats["p_red"] = round(float(stats["p_red"]) / float(total), 3)

            approaches.append(
                ApproachModel(
                    approach_id=a["approach_id"],
                    heading_bucket=a["heading_bucket"],
                    samples_total=len(obs),
                    stop_samples=len(stops),
                    pass_samples=len(passes),
                    p_red_on_approach=(len(stops) + len(gos)) / max(len(obs), 1),
                    median_stop_duration_sec=median(stop_durs) if stop_durs else None,
                    estimated_cycle_sec=cycle,
                    estimated_green_sec=estimated_green,
                    estimated_red_sec=estimated_red,
                    estimated_green_start=min((x.ts for x in gos), default=None),
                    estimated_red_start=min((x.ts for x in stops), default=None),
                    confidence=round(confidence, 3),
                    regime_class=regime,
                    regime_stability_score=round(stability, 3),
                    source_breakdown=source_breakdown,
                    manual_annotation_count=len(linked_annotations),
                    gps_observation_count=len(obs),
                    conflict_flags=conflict_flags,
                    day_part_profiles=dict(day_parts),
                )
            )
        _infer_offsets(approaches)
        intersections.append(
            IntersectionModel(
                intersection_id=c["intersection_id"],
                center_lat=c["center_lat"],
                center_lon=c["center_lon"],
                approaches=approaches,
            )
        )
    return intersections


def _infer_offsets(approaches: list[ApproachModel]) -> None:
    if len(approaches) < 2:
        return
    for i, a in enumerate(approaches):
        for b in approaches[i + 1 :]:
            if a.estimated_cycle_sec and b.estimated_cycle_sec:
                off = abs((a.estimated_red_sec or 0) - (b.estimated_red_sec or 0))
                conf = min(a.confidence, b.confidence) * 0.8
                a.estimated_phase_offset_sec = off
                b.estimated_phase_offset_sec = off
                a.estimated_phase_offset_confidence = conf
                b.estimated_phase_offset_confidence = conf

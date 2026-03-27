from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from traffic_analyzer.annotations.manual_phase import extract_manual_annotations, link_annotations
from traffic_analyzer.clustering.intersections import cluster_observations
from traffic_analyzer.config import AnalyzerConfig
from traffic_analyzer.events.detector import detect_observations, link_comments
from traffic_analyzer.inference.model_builder import build_model
from traffic_analyzer.io.jsonio import read_json, write_json, write_jsonl
from traffic_analyzer.normalization.points import normalize_points
from traffic_analyzer.overrides.manager import apply_overrides, load_manual_knowledge, load_overrides
from traffic_analyzer.parsing.session_loader import load_sessions


def build_pipeline(
    sessions_dir: Path,
    artifacts_dir: Path,
    config_path: Path | None = None,
    overrides_path: Path | None = None,
    manual_knowledge_path: Path | None = None,
) -> dict:
    cfg = AnalyzerConfig.load(config_path)
    sessions = load_sessions(sessions_dir)
    all_observations = []
    all_annotations = []
    for s in sessions:
        points = normalize_points(s.points, cfg.normalization)
        obs = detect_observations(points, cfg.events)
        link_comments(s.comments, obs, cfg.parser)
        anns = extract_manual_annotations(s.comments)
        link_annotations(anns, obs, cfg.parser)
        all_observations.extend(obs)
        all_annotations.extend(anns)

    clustered = cluster_observations(all_observations, cfg.clustering)
    model = build_model(clustered, all_annotations, cfg.inference)

    manual_knowledge = load_manual_knowledge(manual_knowledge_path)
    # knowledge currently informational and for future incremental merging
    _ = manual_knowledge
    overrides = load_overrides(overrides_path)
    model = apply_overrides(model, overrides)

    write_jsonl(artifacts_dir / "observations.jsonl", all_observations)
    write_json(artifacts_dir / "intersections.json", model)
    write_json(artifacts_dir / "traffic_lights_model.json", model)
    write_json(
        artifacts_dir / "intersections.geojson",
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [i.center_lon, i.center_lat]},
                    "properties": {"intersection_id": i.intersection_id, "approaches": len(i.approaches)},
                }
                for i in model
            ],
        },
    )

    conflicts = []
    for i in model:
        for a in i.approaches:
            if a.conflict_flags:
                conflicts.append({"intersection_id": i.intersection_id, "approach_id": a.approach_id, "flags": a.conflict_flags})

    summary = {
        "sessions_total": len(sessions),
        "observations_total": len(all_observations),
        "annotations_total": len(all_annotations),
        "intersections_total": len(model),
        "confidence_distribution": {
            "high": sum(1 for i in model for a in i.approaches if a.confidence >= 0.75),
            "medium": sum(1 for i in model for a in i.approaches if 0.4 <= a.confidence < 0.75),
            "low": sum(1 for i in model for a in i.approaches if a.confidence < 0.4),
        },
    }
    write_json(artifacts_dir / "analysis_summary.json", summary)
    write_json(artifacts_dir / "conflicts.json", conflicts)
    write_json(
        artifacts_dir / "manual_phase_knowledge_snapshot.json",
        [asdict(a) for a in all_annotations],
    )
    return {
        "model": model,
        "annotations": all_annotations,
        "summary": summary,
    }


def load_model(path: Path):
    return read_json(path, default=[])

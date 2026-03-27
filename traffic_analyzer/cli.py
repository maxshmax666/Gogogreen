from __future__ import annotations

import argparse
import json
from pathlib import Path

from traffic_analyzer.config import AnalyzerConfig
from traffic_analyzer.explain.reports import explain_annotation, explain_approach, explain_intersection
from traffic_analyzer.io.jsonio import read_json, write_json
from traffic_analyzer.parsing.session_loader import load_sessions
from traffic_analyzer.pipeline import build_pipeline
from traffic_analyzer.prediction.next_light import predict_next_light, prediction_to_dict
from traffic_analyzer.prediction.route_prediction import predict_route
from traffic_analyzer.routing.interfaces import Route, RoutePoint


def _load_intersections(model_path: Path):
    return read_json(model_path, default=[])


def _dict_to_intersections(raw: list[dict]):
    from traffic_analyzer.models.schemas import ApproachModel, IntersectionModel

    intersections = []
    for i in raw:
        approaches = [ApproachModel(**a) for a in i.get("approaches", [])]
        intersections.append(
            IntersectionModel(
                intersection_id=i["intersection_id"],
                center_lat=i["center_lat"],
                center_lon=i["center_lon"],
                approaches=approaches,
                disabled=i.get("disabled", False),
                label=i.get("label"),
                notes=i.get("notes"),
            )
        )
    return intersections


def main() -> None:
    parser = argparse.ArgumentParser(prog="traffic_analyzer")
    sub = parser.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--sessions-dir", required=True)
    b.add_argument("--artifacts-dir", required=True)
    b.add_argument("--config", default="config/defaults.json")
    b.add_argument("--overrides", default="config/traffic_lights_overrides.json")
    b.add_argument("--manual-knowledge", default="config/manual_phase_knowledge.json")

    v = sub.add_parser("validate")
    v.add_argument("--sessions-dir", required=True)

    vc = sub.add_parser("validate-comments")
    vc.add_argument("--sessions-dir", required=True)

    pn = sub.add_parser("predict-next")
    pn.add_argument("--model", required=True)
    pn.add_argument("--lat", type=float, required=True)
    pn.add_argument("--lon", type=float, required=True)
    pn.add_argument("--heading", type=float, required=True)
    pn.add_argument("--speed", type=float, required=True)
    pn.add_argument("--timestamp", type=int, required=True)

    pr = sub.add_parser("predict-route")
    pr.add_argument("--model", required=True)
    pr.add_argument("--route", required=True)
    pr.add_argument("--timestamp", type=int, required=True)

    ei = sub.add_parser("explain-intersection")
    ei.add_argument("--model", required=True)
    ei.add_argument("--intersection-id", required=True)

    ea = sub.add_parser("explain-approach")
    ea.add_argument("--model", required=True)
    ea.add_argument("--intersection-id", required=True)
    ea.add_argument("--approach-id", required=True)

    eann = sub.add_parser("explain-annotation")
    eann.add_argument("--artifacts-dir", required=True)
    eann.add_argument("--annotation-id", required=True)

    args = parser.parse_args()

    if args.cmd == "build":
        res = build_pipeline(
            sessions_dir=Path(args.sessions_dir),
            artifacts_dir=Path(args.artifacts_dir),
            config_path=Path(args.config),
            overrides_path=Path(args.overrides),
            manual_knowledge_path=Path(args.manual_knowledge),
        )
        print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
        return

    if args.cmd == "validate":
        sessions = load_sessions(Path(args.sessions_dir))
        print(json.dumps({"valid_sessions": len(sessions)}, indent=2))
        return

    if args.cmd == "validate-comments":
        from traffic_analyzer.annotations.manual_phase import extract_manual_annotations

        sessions = load_sessions(Path(args.sessions_dir))
        parsed = sum(len(extract_manual_annotations(s.comments)) for s in sessions)
        print(json.dumps({"sessions": len(sessions), "manual_annotations_parsed": parsed}, ensure_ascii=False, indent=2))
        return

    raw = _load_intersections(Path(args.model))
    intersections = _dict_to_intersections(raw)

    if args.cmd == "predict-next":
        cfg = AnalyzerConfig()
        pred = predict_next_light(intersections, args.lat, args.lon, args.heading, args.speed, args.timestamp, cfg.guidance)
        print(json.dumps(prediction_to_dict(pred), ensure_ascii=False, indent=2))
        return

    if args.cmd == "predict-route":
        route_raw = read_json(Path(args.route), default={})
        points = [RoutePoint(lat=p[0], lon=p[1]) for p in route_raw.get("points", [])]
        route = Route(points=points)
        cfg = AnalyzerConfig()
        preds = predict_route(route, intersections, args.timestamp, cfg.guidance)
        print(json.dumps(preds, ensure_ascii=False, indent=2))
        return

    if args.cmd == "explain-intersection":
        print(json.dumps(explain_intersection(intersections, args.intersection_id), ensure_ascii=False, indent=2))
        return

    if args.cmd == "explain-approach":
        print(json.dumps(explain_approach(intersections, args.intersection_id, args.approach_id), ensure_ascii=False, indent=2))
        return

    if args.cmd == "explain-annotation":
        anns = read_json(Path(args.artifacts_dir) / "manual_phase_knowledge_snapshot.json", default=[])
        from traffic_analyzer.models.schemas import ManualPhaseAnnotation

        annotations = [ManualPhaseAnnotation(**a) for a in anns]
        print(json.dumps(explain_annotation(annotations, args.annotation_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

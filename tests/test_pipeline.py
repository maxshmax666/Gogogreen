from __future__ import annotations

import json
from pathlib import Path

from traffic_analyzer.annotations.manual_phase import parse_manual_phase_text
from traffic_analyzer.clustering.intersections import cluster_observations
from traffic_analyzer.config import AnalyzerConfig
from traffic_analyzer.events.detector import detect_observations
from traffic_analyzer.inference.model_builder import build_model
from traffic_analyzer.models.schemas import GPSPoint, Observation
from traffic_analyzer.normalization.points import normalize_points
from traffic_analyzer.overrides.manager import apply_overrides
from traffic_analyzer.parsing.session_loader import load_sessions
from traffic_analyzer.pipeline import build_pipeline
from traffic_analyzer.prediction.next_light import predict_next_light


def _mk_points() -> list[GPSPoint]:
    return [
        GPSPoint("s", 1000, 55.0, 37.0, 8, 8, 0),
        GPSPoint("s", 6000, 55.0001, 37.0, 8, 0.1, 0),
        GPSPoint("s", 12000, 55.0001, 37.0, 8, 0.0, 0),
        GPSPoint("s", 18000, 55.0001, 37.0, 8, 0.0, 0),
        GPSPoint("s", 24000, 55.0002, 37.0, 8, 6.0, 0),
    ]


def test_optional_comments_missing(tmp_path: Path) -> None:
    sdir = tmp_path / "sessions" / "a"
    sdir.mkdir(parents=True)
    (sdir / "meta.json").write_text('{"session_id":"x"}', encoding="utf-8")
    (sdir / "points.jsonl").write_text('{"timestamp":1,"latitude":1,"longitude":1}\n', encoding="utf-8")
    sessions = load_sessions(tmp_path / "sessions")
    assert len(sessions) == 1
    assert sessions[0].comments == []


def test_nested_session_dir_and_csv_points_fallback(tmp_path: Path) -> None:
    sdir = tmp_path / "sessions" / "2026-03-27" / "gps-1"
    sdir.mkdir(parents=True)
    (sdir / "meta.json").write_text(
        json.dumps(
            {
                "session_id": "gps-1",
                "points_file_csv": "points.csv",
                "sensor_events_file_jsonl": "sensor_events.jsonl",
            }
        ),
        encoding="utf-8",
    )
    (sdir / "points.csv").write_text(
        "client_timestamp_ms,latitude,longitude,accuracy_m,speed_mps,heading_deg\n"
        "1700000000000,55.75,37.61,5,3.2,45\n",
        encoding="utf-8",
    )
    (sdir / "sensor_events.jsonl").write_text(
        '{"client_timestamp_ms":1700000001000,"latitude":55.75,"longitude":37.61,"text":"red 40"}\n',
        encoding="utf-8",
    )
    sessions = load_sessions(tmp_path / "sessions")
    assert len(sessions) == 1
    assert len(sessions[0].points) == 1
    assert sessions[0].points[0].ts == 1700000000000
    assert len(sessions[0].comments) == 1


def test_speed_heading_fallback() -> None:
    points = _mk_points()
    points[1].speed_mps = 0
    points[1].source_speed = "derived"
    points[1].heading_deg = 0
    points[1].source_heading = "derived"
    cfg = AnalyzerConfig().normalization
    out = normalize_points(points, cfg)
    assert out[1].speed_mps > 0
    assert 0 <= out[1].heading_deg <= 360


def test_stop_go_detection() -> None:
    ncfg = AnalyzerConfig().normalization
    ncfg.smoothing_window = 2
    points = normalize_points(_mk_points(), ncfg)
    ecfg = AnalyzerConfig().events
    ecfg.low_speed_mps = 1.5
    ecfg.move_speed_mps = 2.5
    obs = detect_observations(points, ecfg)
    assert any(o.event_type == "stop_start" for o in obs)
    assert any(o.event_type in {"go_start", "pass_through"} for o in obs)


def test_clustering() -> None:
    obs = [
        Observation("o1", "s", "stop_start", 1, 55.0, 37.0, 0, 0),
        Observation("o2", "s", "go_start", 2, 55.0001, 37.0001, 10, 3),
        Observation("o3", "s", "go_start", 3, 56.0, 38.0, 180, 4),
        Observation("o4", "s", "stop_start", 4, 56.0001, 38.0001, 190, 0),
    ]
    clusters = cluster_observations(obs, AnalyzerConfig().clustering)
    assert len(clusters) >= 1


def test_manual_comment_parsing() -> None:
    p, sec, sem, conf = parse_manual_phase_text("красный 45")
    assert p == "red" and sec == 45 and sem in {"remaining_time", "phase_duration"} and conf > 0.5
    p2, sec2, _, _ = parse_manual_phase_text("g35")
    assert p2 == "green" and sec2 == 35


def test_override_precedence() -> None:
    clustered = [{"intersection_id": "tl_0", "center_lat": 1.0, "center_lon": 1.0, "approaches": [{"approach_id": "tl_0_a_0", "heading_bucket": 0, "observations": []}]}]
    model = build_model(clustered, [], AnalyzerConfig().inference)
    out = apply_overrides(model, {"intersections": {"tl_0": {"approaches": {"tl_0_a_0": {"force_cycle_sec": 70}}}}})
    assert out[0].approaches[0].estimated_cycle_sec == 70


def test_prediction_insufficient_data() -> None:
    pred = predict_next_light([], 55, 37, 0, 10, 1700000000000, AnalyzerConfig().guidance)
    assert pred.next_light_id is None
    assert pred.recommendation == "no_reliable_advice"


def test_build_pipeline_integration(tmp_path: Path) -> None:
    root = Path("fixtures/sessions")
    out = tmp_path / "artifacts"
    result = build_pipeline(root, out, Path("config/defaults.json"), Path("config/traffic_lights_overrides.json"), Path("config/manual_phase_knowledge.json"))
    assert (out / "traffic_lights_model.json").exists()
    assert result["summary"]["sessions_total"] >= 1


def test_day_part_profiles_and_conflict() -> None:
    clustered = [{"intersection_id": "tl_0", "center_lat": 1.0, "center_lon": 1.0, "approaches": [{"approach_id": "tl_0_a_0", "heading_bucket": 0, "observations": [
        Observation("o1", "s", "go_start", 1700000000000, 1,1,0,2,stop_duration_sec=60),
        Observation("o2", "s", "go_start", 1700000060000, 1,1,0,2,stop_duration_sec=58),
        Observation("o3", "s", "go_start", 1700000120000, 1,1,0,2,stop_duration_sec=62),
    ]}]}]
    model = build_model(clustered, [], AnalyzerConfig().inference)
    assert model[0].approaches[0].day_part_profiles


def test_reverse_direction_phase_offset() -> None:
    clustered = [{"intersection_id": "tl_0", "center_lat": 1.0, "center_lon": 1.0, "approaches": [
        {"approach_id": "tl_0_a_0", "heading_bucket": 0, "observations": [Observation("o1", "s", "go_start", 10000,1,1,0,2,stop_duration_sec=40),Observation("o2","s","go_start",70000,1,1,0,2,stop_duration_sec=42),Observation("o3","s","go_start",130000,1,1,0,2,stop_duration_sec=41),Observation("o4","s","go_start",190000,1,1,0,2,stop_duration_sec=43)]},
        {"approach_id": "tl_0_a_4", "heading_bucket": 4, "observations": [Observation("o5", "s", "go_start", 40000,1,1,180,2,stop_duration_sec=30),Observation("o6","s","go_start",100000,1,1,180,2,stop_duration_sec=32),Observation("o7","s","go_start",160000,1,1,180,2,stop_duration_sec=31),Observation("o8","s","go_start",220000,1,1,180,2,stop_duration_sec=33)]},
    ]}]
    model = build_model(clustered, [], AnalyzerConfig().inference)
    assert model[0].approaches[0].estimated_phase_offset_sec is not None

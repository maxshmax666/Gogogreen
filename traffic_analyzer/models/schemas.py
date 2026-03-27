from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


Phase = Literal["red", "green", "yellow", "unknown"]
SemanticType = Literal["remaining_time", "phase_duration", "uncertain"]
RegimeClass = Literal[
    "unknown",
    "sparse_observations",
    "probable_signalized",
    "stable_fixed_cycle",
    "variable_cycle",
    "manually_verified",
]


@dataclass(slots=True)
class GPSPoint:
    session_id: str
    ts: int
    lat: float
    lon: float
    accuracy_m: float
    speed_mps: float
    heading_deg: float
    source_speed: str = "device"
    source_heading: str = "device"
    smoothed_speed_mps: float = 0.0
    smoothed_heading_deg: float = 0.0


@dataclass(slots=True)
class Comment:
    comment_id: str
    session_id: str
    ts: int
    lat: float
    lon: float
    text: str


@dataclass(slots=True)
class Observation:
    observation_id: str
    session_id: str
    event_type: Literal[
        "approach",
        "stop_start",
        "go_start",
        "pass_through",
        "likely_queue",
        "likely_non_signal_stop",
    ]
    ts: int
    lat: float
    lon: float
    heading_deg: float
    speed_mps: float
    stop_duration_sec: float | None = None
    near_session_start: bool = False
    near_session_end: bool = False
    quality_weight: float = 1.0
    linked_comment_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ManualPhaseAnnotation:
    annotation_id: str
    session_id: str
    ts: int
    lat: float
    lon: float
    heading_deg: float
    raw_text: str
    parsed_phase: Phase
    parsed_seconds: float | None
    semantic_type: SemanticType
    linked_observation_id: str | None = None
    linked_intersection_id: str | None = None
    linked_approach_id: str | None = None
    confidence: float = 0.0


@dataclass(slots=True)
class ApproachModel:
    approach_id: str
    heading_bucket: int
    samples_total: int
    stop_samples: int
    pass_samples: int
    p_red_on_approach: float
    median_stop_duration_sec: float | None
    estimated_cycle_sec: float | None
    estimated_green_sec: float | None
    estimated_red_sec: float | None
    estimated_green_start: int | None
    estimated_red_start: int | None
    confidence: float
    regime_class: RegimeClass
    regime_stability_score: float
    source_breakdown: dict[str, int]
    manual_annotation_count: int
    gps_observation_count: int
    conflict_flags: list[str]
    estimated_phase_offset_sec: float | None = None
    estimated_phase_offset_confidence: float = 0.0
    day_part_profiles: dict[str, dict[str, float | int | None]] = field(default_factory=dict)


@dataclass(slots=True)
class IntersectionModel:
    intersection_id: str
    center_lat: float
    center_lon: float
    approaches: list[ApproachModel]
    disabled: bool = False
    label: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class NextLightPrediction:
    next_light_id: str | None
    approach_id: str | None
    distance_m: float | None
    eta_sec: float | None
    predicted_phase_at_eta: Phase
    time_to_phase_change_sec: float | None
    recommendation: Literal[
        "hold_speed",
        "slow_down",
        "slight_accelerate",
        "no_reliable_advice",
    ]
    target_speed_kmh: float | None
    target_speed_range_kmh: tuple[float, float] | None
    confidence: float
    confidence_breakdown: dict[str, float]
    explanation: str

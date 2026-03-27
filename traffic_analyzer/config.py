from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass(slots=True)
class ParserConfig:
    max_comment_link_distance_m: float = 70.0
    max_comment_link_time_sec: float = 40.0


@dataclass(slots=True)
class NormalizationConfig:
    min_accuracy_m: float = 2.0
    max_accuracy_m: float = 100.0
    max_jump_mps: float = 65.0
    smoothing_window: int = 5


@dataclass(slots=True)
class EventConfig:
    low_speed_mps: float = 0.8
    move_speed_mps: float = 2.2
    min_stop_duration_sec: float = 4.0
    max_stop_duration_sec: float = 180.0
    near_session_boundary_sec: float = 45.0


@dataclass(slots=True)
class ClusterConfig:
    geo_eps_m: float = 45.0
    min_samples: int = 2
    heading_bucket_deg: float = 45.0


@dataclass(slots=True)
class InferenceConfig:
    time_slot_minutes: int = 15
    min_samples_for_cycle: int = 4
    strong_manual_threshold: int = 4
    stable_std_threshold_sec: float = 3.0


@dataclass(slots=True)
class GuidanceConfig:
    min_speed_kmh: float = 15.0
    max_speed_kmh: float = 80.0
    eta_horizon_sec: float = 180.0


@dataclass(slots=True)
class AnalyzerConfig:
    parser: ParserConfig = field(default_factory=ParserConfig)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    events: EventConfig = field(default_factory=EventConfig)
    clustering: ClusterConfig = field(default_factory=ClusterConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    guidance: GuidanceConfig = field(default_factory=GuidanceConfig)

    @staticmethod
    def load(path: Path | None) -> "AnalyzerConfig":
        if path is None or not path.exists():
            return AnalyzerConfig()
        raw = json.loads(path.read_text(encoding="utf-8"))
        cfg = AnalyzerConfig()
        for section_name, section_values in raw.items():
            section = getattr(cfg, section_name, None)
            if section is None or not isinstance(section_values, dict):
                continue
            for key, value in section_values.items():
                if hasattr(section, key):
                    setattr(section, key, value)
        return cfg

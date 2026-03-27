from __future__ import annotations

from pathlib import Path

from traffic_analyzer.io.jsonio import read_json
from traffic_analyzer.models.schemas import IntersectionModel


def load_overrides(path: Path | None) -> dict:
    if path is None:
        return {}
    return read_json(path, default={}) or {}


def load_manual_knowledge(path: Path | None) -> dict:
    if path is None:
        return {}
    return read_json(path, default={}) or {}


def apply_overrides(intersections: list[IntersectionModel], overrides: dict) -> list[IntersectionModel]:
    by_id = overrides.get("intersections", {})
    for i in intersections:
        ov = by_id.get(i.intersection_id)
        if not ov:
            continue
        i.disabled = bool(ov.get("disabled", i.disabled))
        i.label = ov.get("label", i.label)
        i.notes = ov.get("notes", i.notes)
        for a in i.approaches:
            aov = (ov.get("approaches") or {}).get(a.approach_id, {})
            if "force_cycle_sec" in aov:
                a.estimated_cycle_sec = float(aov["force_cycle_sec"])
            if "force_green_sec" in aov:
                a.estimated_green_sec = float(aov["force_green_sec"])
            if "force_red_sec" in aov:
                a.estimated_red_sec = float(aov["force_red_sec"])
            if aov.get("manually_verified"):
                a.regime_class = "manually_verified"
                a.confidence = max(a.confidence, 0.9)
    return intersections

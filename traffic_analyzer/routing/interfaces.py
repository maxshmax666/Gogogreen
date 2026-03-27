from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class RoutePoint:
    lat: float
    lon: float


@dataclass(slots=True)
class Route:
    points: list[RoutePoint]


class Router(Protocol):
    def build_route(self, start_lat: float, start_lon: float, destination: str) -> Route: ...


class MockRouter:
    def build_route(self, start_lat: float, start_lon: float, destination: str) -> Route:
        _ = destination
        return Route(points=[RoutePoint(start_lat, start_lon)])

from __future__ import annotations

from collections import defaultdict

from traffic_analyzer.config import ClusterConfig
from traffic_analyzer.models.schemas import Observation
from traffic_analyzer.utils.geo import haversine_m, heading_bucket


def _dbscan_points(observations: list[Observation], eps_m: float, min_samples: int) -> list[list[Observation]]:
    clusters: list[list[Observation]] = []
    visited: set[int] = set()
    for i, o in enumerate(observations):
        if i in visited:
            continue
        visited.add(i)
        neighbors = [j for j, x in enumerate(observations) if haversine_m(o.lat, o.lon, x.lat, x.lon) <= eps_m]
        if len(neighbors) < min_samples:
            continue
        cluster_idx = set(neighbors)
        queue = list(neighbors)
        while queue:
            q = queue.pop()
            if q in visited:
                continue
            visited.add(q)
            n2 = [k for k, x in enumerate(observations) if haversine_m(observations[q].lat, observations[q].lon, x.lat, x.lon) <= eps_m]
            if len(n2) >= min_samples:
                for n in n2:
                    if n not in cluster_idx:
                        cluster_idx.add(n)
                        queue.append(n)
        clusters.append([observations[k] for k in sorted(cluster_idx)])
    return clusters


def cluster_observations(observations: list[Observation], cfg: ClusterConfig) -> list[dict]:
    candidates = [o for o in observations if o.event_type in {"go_start", "stop_start", "pass_through"}]
    clusters = _dbscan_points(candidates, cfg.geo_eps_m, cfg.min_samples)
    result: list[dict] = []
    for i, cluster in enumerate(clusters):
        center_lat = sum(x.lat for x in cluster) / len(cluster)
        center_lon = sum(x.lon for x in cluster) / len(cluster)
        by_bucket: dict[int, list[Observation]] = defaultdict(list)
        for obs in cluster:
            by_bucket[heading_bucket(obs.heading_deg, cfg.heading_bucket_deg)].append(obs)
        approaches = []
        for b, obs_list in by_bucket.items():
            approaches.append(
                {
                    "approach_id": f"tl_{i:03d}_a_{b}",
                    "heading_bucket": b,
                    "observations": obs_list,
                }
            )
        result.append(
            {
                "intersection_id": f"tl_{i:03d}",
                "center_lat": center_lat,
                "center_lon": center_lon,
                "approaches": approaches,
            }
        )
    return result

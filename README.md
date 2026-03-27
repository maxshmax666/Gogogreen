# traffic_analyzer

Production-oriented foundation for GPS session analysis, traffic-light phase inference, next-light prediction, and safe advisory speed guidance.

## Architecture (MVP + future-ready)

```
parsing -> normalization -> events -> clustering -> annotations -> inference -> prediction/explain
                                 |                          |
                                 +---- artifacts store -----+
```

- **MVP now**: robust offline rebuild pipeline + explainable model + CLI + tests.
- **Future-ready**: routing abstraction (`routing.interfaces.Router`), persistent manual knowledge layer, override layer, JSON artifacts shaped as DTOs so storage can migrate to SQLite/Postgres.

### Key trade-offs
- Rebuild-first (idempotent) over full incremental updates for reliability and easier correctness.
- Conservative confidence logic (returns low confidence/null estimates when sparse).
- Manual phase annotations are strong evidence but conflict-aware (do not blindly overwrite GPS evidence).

## Requirements
- Python **3.11+**
- `pydantic>=2.7,<3`
- Dev: `pytest>=8.2,<9`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

## Session input formats
Loader supports both layouts:

- Flat: `sessions/<session_id>/meta.json + points.jsonl`
- Nested by date: `sessions/YYYY-MM-DD/<session_id>/meta.json + points.jsonl`

Also supported for points ingestion:

- `points.jsonl` (default)
- `points.csv` fallback (or explicit `points_file_csv` in `meta.json`)

For comments/events:

- `comments.jsonl` (default)
- `sensor_events.jsonl` via `sensor_events_file_jsonl` in `meta.json`

## CLI

```bash
python -m traffic_analyzer build --sessions-dir ./sessions --artifacts-dir ./artifacts
python -m traffic_analyzer validate --sessions-dir ./sessions
python -m traffic_analyzer validate-comments --sessions-dir ./sessions
python -m traffic_analyzer predict-next --model ./artifacts/traffic_lights_model.json --lat 55.75 --lon 37.61 --heading 30 --speed 10 --timestamp 1700000000000
python -m traffic_analyzer predict-route --model ./artifacts/traffic_lights_model.json --route ./route.json --timestamp 1700000000000
python -m traffic_analyzer explain-intersection --model ./artifacts/traffic_lights_model.json --intersection-id tl_000
python -m traffic_analyzer explain-approach --model ./artifacts/traffic_lights_model.json --intersection-id tl_000 --approach-id tl_000_a_0
python -m traffic_analyzer explain-annotation --artifacts-dir ./artifacts --annotation-id ann_s1_c_0
```

## Artifacts
- `artifacts/observations.jsonl`
- `artifacts/intersections.json`
- `artifacts/intersections.geojson`
- `artifacts/traffic_lights_model.json`
- `artifacts/analysis_summary.json`
- `artifacts/conflicts.json`
- `artifacts/manual_phase_knowledge_snapshot.json`

## Manual signals
Supported strong phase comment examples:
- `red 45`, `green 35`, `r45`, `g35`
- `красный 45`, `зелёный 35`
- `red=45`, `green:35`

Parser output includes:
- `parsed_phase`
- `parsed_seconds`
- `semantic_type` (`remaining_time` / `phase_duration` / `uncertain`)

## Safety and guidance
Recommendations are advisory only and bounded by config speed limits. If confidence is low, system returns `no_reliable_advice`.

## Testing

```bash
pytest -q
```

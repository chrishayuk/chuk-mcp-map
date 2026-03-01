# chuk-mcp-map Roadmap

## Current State (v1.1.0)

**Working:** 4 tools for interactive geospatial visualisation — GeoJSON layers, bounding boxes, image overlays, tile layers, marker clustering, click popups, and smart auto-popups with key filtering, priority ordering, and compound titles.

**Test Stats:** 158 tests, 99% coverage. All checks pass (ruff, mypy, bandit, pytest).

**Infrastructure:** pyproject.toml, Makefile, Dockerfile, fly.toml, CI-ready.

**Implemented:** `show_map` (rich multi-layer maps with styling, clustering, auto-popups), `show_geojson` (quick single-layer with auto-popups), `show_bbox` (bounding box highlight), `show_layers` (simplified multi-layer). Smart auto-popup: filters internal keys (`_id`, `fid`, `objectid`), priority-orders fields (name, description, type first), compound titles (`"{name} — {type}"`). Auto-centre/zoom from features or image bounds. 3 layer types: GeoJSON, image overlay, XYZ tiles. 4 basemaps: osm, satellite, terrain, dark. Pure Python — no GDAL, shapely, or rasterio.

---

## Phase 1.0: Core Map Tools (v1.0.0) -- COMPLETE

### 1.0.1 Project Infrastructure

- [x] Initialize git repo with `.gitignore`
- [x] Create `pyproject.toml` with dependencies
- [x] Create `Makefile` with full target set (test, lint, format, typecheck, security, check)
- [x] Add `Dockerfile` (multi-stage, python:3.14-slim)
- [x] Add `fly.toml` for Fly.io deployment
- [x] Add `README.md` with tool reference and examples

### 1.0.2 Core Tools (4 tools)

- [x] `show_map` — full-featured multi-layer map with styling, clustering, popups
- [x] `show_geojson` — quick single-layer map from raw GeoJSON
- [x] `show_bbox` — bounding box highlight on a map
- [x] `show_layers` — simplified multi-layer overview

### 1.0.3 Layer Types

- [x] GeoJSON layers (Point, LineString, Polygon, Multi*, GeometryCollection)
- [x] Image overlay layers (raster positioned by geographic bounds)
- [x] XYZ tile layers (custom basemap tiles)

### 1.0.4 Smart Defaults

- [x] Auto-centre from union of all layer features/image bounds
- [x] Auto-zoom from feature/image extent (log2-based, clamped 1–15)
- [x] Auto-popup from feature properties (name > title > label > first key)
- [x] Default colour palette cycling across layers
- [x] Style key normalisation (camelCase → snake_case)

### 1.0.5 Tests & Documentation

- [x] 118 tests with 99% coverage
- [x] `README.md` — overview, install, usage, tool reference, architecture
- [x] `ROADMAP.md` — this document

---

## Phase 1.1: Enhanced Popups & Labels (v1.1.0) -- PARTIAL

Improve the information density on maps without requiring explicit popup/style configuration.

### 1.1.1 Marker Labels — DEFERRED

Requires `chuk-view-schemas` update for `label_field` on `MapLayer`. Deferred to a future release.

- [ ] Show a short label on the marker itself (not just in the popup) — e.g. city name or temperature
- [ ] `label_field` option in layer definition — which property to display on the marker
- [ ] Auto-detect: use `name` or `label` property if present and short enough

### 1.1.2 Popup Formatting — COMPLETE

- [x] Exclude internal/technical properties (e.g. `_id`, `fid`, `objectid`, `geometry_type`)
- [x] Priority field ordering (name, title, label, description, type, category, status first)
- [x] Compound title generation (`"{name} — {type}"` when both present)
- [x] Format numeric values (e.g. 1234567 → "1,234,567") — `_format_value` helper
- [x] Unit suffixes from property names (e.g. `temp_celsius` → "12 °C") — `_format_value` helper
- [x] Humanize property keys (e.g. `wind_speed` → "Wind Speed") — `_humanize_key` helper
- [x] Add auto-popup to `show_geojson` (previously had no popup)

### 1.1.3 Tests — COMPLETE

- [x] Popup formatting tests (key exclusion, ordering, compound titles, formatting, units)
- [x] 40 new tests (158 total), 99% coverage maintained

---

## Phase 1.2: Heatmaps & Choropleth (v1.2.0)

Add common visualisation modes beyond point markers and polygon fills.

### 1.2.1 Heatmap Layer Type

- [ ] `layer_type: "heatmap"` — render point density as a heatmap
- [ ] `weight_field` option — use a property value as the heat weight (e.g. population, magnitude)
- [ ] Configurable radius, blur, gradient
- [ ] Requires `chuk-view-schemas` update for heatmap layer type

### 1.2.2 Choropleth Styling

- [ ] `style_by` option on GeoJSON layers — colour polygons by a numeric property
- [ ] Built-in colour ramps (sequential, diverging, categorical)
- [ ] Auto-generate legend from value range
- [ ] Useful for: population maps, weather temperature fill, election results

### 1.2.3 Tests & Examples

- [ ] Heatmap layer rendering tests
- [ ] Choropleth colour assignment tests
- [ ] Value range edge cases (all same, NaN, negative)

---

## Phase 2.0: Composition-Ready Features (v2.0.0)

Make the map server excel when composed alongside sibling MCP servers (DEM, STAC, weather, etc.). The LLM orchestrates calls across servers — no server-to-server dependencies. All servers run independently; the model calls DEM/STAC/weather tools to gather data, then passes GeoJSON + properties to the map server for visualisation.

### 2.0.1 Better Data-Dense Maps

- [ ] Improve `show_map` for common composed workflows (e.g. weather + map, STAC + map, DEM + map)
- [ ] Support richer popup body templates (multi-line, sections, units)
- [ ] Conditional marker icons based on a property value (e.g. weather icon per condition)
- [ ] Colour markers by a numeric property (e.g. red=hot, blue=cold for temperature)

### 2.0.2 Timeline / Animation Support

- [ ] `show_timeline_map` tool — animate features over time (e.g. storm track, vessel path)
- [ ] `time_field` option — which property holds the timestamp
- [ ] Playback controls: play/pause, speed, scrub
- [ ] Requires `chuk-view-schemas` update for timeline map type

### 2.0.3 Tests

- [ ] Conditional icon tests
- [ ] Colour-by-property tests
- [ ] Timeline animation data structure tests

---

## Phase 2.1: Export & Sharing (v2.1.0)

Make maps shareable and usable outside the MCP client.

### 2.1.1 Static Image Export

- [ ] `export_map_image` tool — render the current map view as a PNG screenshot
- [ ] Uses headless browser (playwright) or server-side Leaflet rendering
- [ ] Returns artifact reference for download

### 2.1.2 GeoJSON Export

- [ ] `export_geojson` tool — export all layers as a combined GeoJSON FeatureCollection
- [ ] Preserves properties, styles as metadata
- [ ] Importable into QGIS, ArcGIS, Mapbox, kepler.gl

### 2.1.3 Tests

- [ ] Export format validation tests
- [ ] Round-trip: export → reimport matches original features

---

## Phase 3.0: Drawing & Annotation (v3.0.0)

Enable users to create and edit geographic features interactively.

### 3.0.1 Drawing Tools

- [ ] `draw_point` / `draw_polygon` / `draw_line` tools — create features by specifying coordinates or clicking on map
- [ ] `annotate_map` tool — add text labels, arrows, or measurement lines to an existing map
- [ ] Returns updated GeoJSON that can be fed back into other tools

### 3.0.2 Measurement

- [ ] `measure_distance` — great-circle distance between two points
- [ ] `measure_area` — polygon area in km² or hectares
- [ ] Results shown as map annotations

### 3.0.3 Tests

- [ ] Drawing tools create valid GeoJSON
- [ ] Measurement accuracy tests (known distances/areas)

---

## Architecture: Composition over Integration

The map server has **no dependencies** on DEM, STAC, weather, or any other data server. Instead, servers are composed at runtime:

```
LLM (orchestrator)
 ├── weather server  →  get_weather_forecast("London")  →  { temp: "12°C", ... }
 ├── STAC server     →  stac_search(bbox=...)           →  { features: [...] }
 ├── DEM server      →  dem_fetch(bbox=...)             →  { hillshade_url: "..." }
 └── map server      →  show_map(layers=...)            →  interactive map with popups
```

The LLM gathers data from any source, assembles GeoJSON with properties, and calls the map server to render it. Auto-popups ensure the data is always visible — even if the LLM forgets to configure popups.

## Dependencies

| Install | Adds | What |
|---------|------|------|
| `chuk-mcp-map` | chuk-mcp-server, chuk-view-schemas | All tools |

No geo-specific dependencies — GeoJSON handling is pure Python. No GDAL, shapely, or rasterio.

---

## Version Summary

| Version | Key Deliverables |
|---------|------------------|
| 1.0.0 | Initial release: 4 tools, 3 layer types, auto-popup, auto-centre/zoom. 118 tests. |
| 1.1.0 | Phase 1.1: Smart popup formatting — key filtering, priority ordering, compound titles, show_geojson auto-popup. 158 tests. |
| 1.2.0 | Phase 1.2: Heatmap layers, choropleth styling. |
| 2.0.0 | Phase 2.0: Composition-ready features — conditional icons, colour-by-property, timeline maps. |
| 2.1.0 | Phase 2.1: Static image export, GeoJSON export. |
| 3.0.0 | Phase 3.0: Drawing, annotation, measurement tools. |

---

*Last updated: 2026-03*

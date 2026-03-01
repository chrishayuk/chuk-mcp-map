# Chuk MCP Map

**Interactive Geospatial Visualisation MCP Server** -- A generic Model Context Protocol (MCP) server for rendering maps, GeoJSON layers, bounding boxes, and terrain overlays.

> This is a demonstration project provided as-is for learning and testing purposes.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Tests: 158 passed](https://img.shields.io/badge/tests-158%20passed-brightgreen.svg)]()

## Features

This MCP server provides 4 tools for creating interactive map views from GeoJSON data, image overlays, and tile layers.

**All tools return fully-typed Pydantic v2 models** (`MapContent` / `LayersContent`) for type safety and validation.

**Smart auto-popups**: When features have properties (e.g. name, temperature, description), clickable popups are generated automatically -- no explicit popup configuration needed. Internal keys (`_id`, `fid`, `objectid`, etc.) are filtered out, fields are priority-ordered (name, description, type first), and compound titles like "London -- Monument" are generated when both a name and type/category are present.

### Layer Types

| Type | Description | Use Case |
|------|-------------|----------|
| **GeoJSON** (default) | Points, lines, polygons with styling and popups | Feature collections, search results, boundaries |
| **Image overlay** | Raster image positioned by geographic bounds | Satellite thumbnails, heatmaps, historical maps |
| **Tile layer** | XYZ tile URL template | Custom basemaps, elevation tiles, weather layers |

### Tools

| # | Tool | Returns | Description |
|---|------|---------|-------------|
| 1 | `show_map` | `MapContent` | Best for rich maps -- styling, clustering, popups, multiple layers, image/tile overlays |
| 2 | `show_geojson` | `MapContent` | Quick single-layer map -- pass raw GeoJSON, auto-generates popups |
| 3 | `show_bbox` | `MapContent` | Highlight a bounding box on a map |
| 4 | `show_layers` | `LayersContent` | Simple multi-layer map with toggles (no styling or popups) |

## Installation

### Using uv (Recommended)

```bash
# Install from PyPI
uv pip install chuk-mcp-map

# Or clone and install from source
git clone https://github.com/chrishayuk/chuk-mcp-map.git
cd chuk-mcp-map
uv sync --dev
```

### Using pip

```bash
pip install chuk-mcp-map
```

## Usage

### With Claude Desktop

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "map": {
      "command": "uvx",
      "args": ["chuk-mcp-map"]
    }
  }
}
```

Or if installed locally:

```json
{
  "mcpServers": {
    "map": {
      "command": "chuk-mcp-map"
    }
  }
}
```

### Standalone

```bash
# STDIO mode (default, for MCP clients)
uv run chuk-mcp-map

# HTTP mode (for web access)
uv run chuk-mcp-map http
```

### Example Queries

Once configured, you can ask Claude questions like:

- "Show me a map of the top 10 world capitals"
- "Plot these earthquake locations on a map"
- "Highlight the bounding box for the UK on a map"
- "Show GeoJSON from this API response on a map"
- "Overlay these satellite footprints with thumbnails"

## Tool Reference

### 1. `show_map` -- Rich Interactive Map

Best tool when you need clickable popups, styled markers, clustering, multiple layers, or image/tile overlays. Put data into GeoJSON feature properties and popups are auto-generated (or supply an explicit popup template for control).

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `layers` | str (JSON) | *required* | JSON array of layer definitions (see below) |
| `basemap` | str | `"osm"` | Base tiles: `osm`, `satellite`, `terrain`, `dark` |
| `center_lat` | float | auto | Map centre latitude (auto-detected from features) |
| `center_lon` | float | auto | Map centre longitude (auto-detected from features) |
| `zoom` | int | auto | Zoom level 1--15 (auto-calculated from extent) |

**Layer Definition (GeoJSON):**

```json
{
  "id": "cities",
  "label": "UK Weather",
  "features": {
    "type": "FeatureCollection",
    "features": [{
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [-0.12, 51.5] },
      "properties": { "name": "London", "temp": "12°C", "conditions": "Overcast", "wind": "18 km/h" }
    }]
  },
  "style": { "fillColor": "#3388ff", "fillOpacity": 0.4, "color": "#0044cc", "weight": 2 },
  "cluster": true
}
```

Popups are **auto-generated** from feature properties -- clicking a marker shows name, temp, conditions, and wind. To customise, add an explicit `popup` field: `{"title": "{name}", "fields": ["temp", "conditions"]}`.

**Layer Definition (Image Overlay):**

```json
{
  "id": "thumbnail",
  "label": "Satellite Thumbnail",
  "layer_type": "image",
  "image_url": "https://example.com/thumb.jpg",
  "image_bounds": [[south_lat, west_lon], [north_lat, east_lon]],
  "opacity": 0.9,
  "visible": false
}
```

**Layer Definition (Tile Layer):**

```json
{
  "id": "topo",
  "label": "USGS Topo",
  "layer_type": "tiles",
  "tile_url": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
  "tile_attribution": "USGS The National Map",
  "tile_min_zoom": 0,
  "tile_max_zoom": 16
}
```

### 2. `show_geojson` -- Quick Single-Layer Map

Fastest way to get a map -- pass raw GeoJSON and everything is auto-configured. Auto-generates clickable popups from feature properties. Use `show_map` for full control over styling, clustering, and popup templates.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `geojson` | str | *required* | GeoJSON string (FeatureCollection, Feature, or bare Geometry) |
| `label` | str | `"Features"` | Layer name shown in the legend |
| `basemap` | str | `"osm"` | Base tiles: `osm`, `satellite`, `terrain`, `dark` |
| `fill_color` | str | -- | Polygon/circle fill colour (hex) |
| `stroke_color` | str | -- | Line/polygon stroke colour (hex) |
| `cluster` | bool | `false` | Cluster point markers |

### 3. `show_bbox` -- Bounding Box Map

Display a bounding box as a highlighted polygon. Useful for showing search extents or raster coverage.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `west` | float | *required* | Western longitude (decimal degrees, WGS84) |
| `south` | float | *required* | Southern latitude |
| `east` | float | *required* | Eastern longitude |
| `north` | float | *required* | Northern latitude |
| `label` | str | `"Area"` | Layer label in the legend |
| `basemap` | str | `"osm"` | Base tiles |
| `fill_color` | str | `"#3388ff"` | Polygon fill colour (hex) |

### 4. `show_layers` -- Lightweight Multi-Layer

Simplified multi-layer overview without per-layer styling or popups. Use `show_map` when you need styling and interactivity.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `layers` | str (JSON) | *required* | JSON array of `{id, label, features}` objects |
| `title` | str | -- | Optional map title |
| `basemap` | str | `"osm"` | Base tiles |
| `center_lat` | float | auto | Map centre latitude |
| `center_lon` | float | auto | Map centre longitude |
| `zoom` | int | auto | Zoom level 1--15 |

## Architecture

```
src/chuk_mcp_map/
    __init__.py        # Package version
    server.py          # MCP server, 4 tool handlers, CLI entry point
    helpers.py         # GeoJSON parsing, bbox, centre/zoom, layer builders
```

Built on top of **chuk-mcp-server** with views from **chuk-view-schemas**:

- **Decorators**: `@map_tool` and `@layers_tool` from `chuk_view_schemas.chuk_mcp`
- **Return types**: `MapContent` and `LayersContent` (Pydantic v2 models)
- **Transport**: STDIO (default for MCP clients) or HTTP (`--http` flag)
- **No geo dependencies**: Pure Python GeoJSON handling -- no GDAL, shapely, or rasterio

Used by [chuk-mcp-stac](https://github.com/chrishayuk/chuk-mcp-stac), [chuk-mcp-dem](https://github.com/chrishayuk/chuk-mcp-dem), and any other server that needs a map UI.

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/chrishayuk/chuk-mcp-map.git
cd chuk-mcp-map

# Install with uv (recommended)
uv sync --dev

# Or with pip
pip install -e ".[dev]"
```

### Running Tests

```bash
make test              # Run 158 tests
make test-cov          # Run tests with coverage
make coverage-report   # Show coverage report
```

### Code Quality

```bash
make lint      # Run linters
make format    # Auto-format code
make typecheck # Run type checking
make security  # Run security checks
make check     # Run all checks (lint, typecheck, security, test)
```

### Building

```bash
make build         # Build package
make docker-build  # Build Docker image
make docker-run    # Run Docker container
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Apache License 2.0 -- See [LICENSE](LICENSE) for details.

## Acknowledgments

- [Leaflet](https://leafletjs.com/) for the map rendering engine
- [Model Context Protocol](https://modelcontextprotocol.io/) for the MCP specification
- [Anthropic](https://www.anthropic.com/) for Claude and MCP support

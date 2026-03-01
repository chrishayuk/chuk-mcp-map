"""Map MCP Server — interactive geospatial visualisation.

Provides four tools for creating map views:

- show_map      — Full-featured map from one or more GeoJSON layers with
                  optional styling, clustering, and click popups.
- show_geojson  — Easiest path: pass raw GeoJSON, get an interactive map.
- show_bbox     — Highlight a geographic bounding box on a map.
- show_layers   — Simplified multi-layer overview (no styling/popups).

Built with chuk-mcp-server; renders via the chuk-view-schemas map/layers views.
Used by chuk-mcp-stac, chuk-mcp-dem, and any other server that needs a map UI.
"""

import logging
import sys
from typing import Optional

from chuk_mcp_server import ChukMCPServer
from chuk_view_schemas.layers import LayersCenter, LayersContent
from chuk_view_schemas.map import ClusterConfig, LayerStyle, MapCenter, MapContent, MapControls
from chuk_view_schemas.chuk_mcp import layers_tool, map_tool

from .helpers import (
    LAYER_COLOURS,
    auto_center_zoom,
    bbox_to_feature_collection,
    build_layer_style,
    build_layers_layer,
    build_map_layer,
    calculate_center,
    calculate_zoom,
    calculate_zoom_from_bbox,
    ensure_feature_collection,
    parse_geojson,
    parse_layer_defs,
)

# ---------------------------------------------------------------------------
# Logging — minimal in STDIO mode to keep the JSON-RPC stream clean
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s:%(name)s:%(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = ChukMCPServer(
    name="chuk-mcp-map",
    version="1.0.0",
    title="Map Server",
    description=(
        "Interactive geospatial visualisation — GeoJSON layers, bounding boxes, "
        "terrain overlays, satellite imagery footprints, and more."
    ),
)

_VALID_BASEMAPS = {"osm", "satellite", "terrain", "dark"}
_DEFAULT_CONTROLS = MapControls(zoom=True, layers=True, scale=True, fullscreen=True)


def _resolve_basemap(basemap: str) -> str:
    return basemap if basemap in _VALID_BASEMAPS else "osm"


# ---------------------------------------------------------------------------
# Tool: show_map
# ---------------------------------------------------------------------------


@map_tool(
    mcp,
    "show_map",
    description=(
        "Render an interactive map from one or more GeoJSON, image overlay, or tile layers. "
        "Each layer supports custom styling, marker clustering, and click popups. "
        'GeoJSON layer: {"id":"l1","label":"Sites","features":{...GeoJSON...},'
        '"style":{"fillColor":"#3388ff","fillOpacity":0.4},"cluster":false,'
        '"popup":{"title":"{name}","fields":["name","type"]}}. '
        'Image overlay: {"id":"img","label":"Thumbnail","layer_type":"image",'
        '"image_url":"https://...","image_bounds":[[south_lat,west_lon],[north_lat,east_lon]],'
        '"opacity":0.9,"visible":false}. '
        'Tile layer: {"id":"tiles","label":"Custom Tiles","layer_type":"tiles",'
        '"tile_url":"https://example.com/{z}/{x}/{y}.png","tile_attribution":"Source"}. '
        "basemap: osm (default), satellite, terrain, dark. "
        "center_lat/center_lon and zoom are auto-computed from features/bounds if omitted."
    ),
    read_only_hint=True,
)
async def show_map(
    layers: str,
    basemap: str = "osm",
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    zoom: Optional[int] = None,
) -> MapContent:
    """Render an interactive map from one or more GeoJSON, image overlay, or tile layers.

    Args:
        layers: JSON array of layer definition objects. Each object supports:
            - id (str): Unique layer ID.
            - label (str): Human-readable name shown in the legend.
            - layer_type (str, optional): "geojson" (default), "image", or "tiles".
            GeoJSON layer fields (layer_type omitted or "geojson"):
            - features (dict | str): GeoJSON FeatureCollection, Feature, or Geometry.
            - style (dict, optional): Styling keys — fillColor, fillOpacity, color,
              weight, icon (URL), radius (pixels for circle markers).
            - cluster (bool | dict, optional): Enable marker clustering. Pass true for
              defaults or {"enabled": true, "radius": 80}.
            - popup (dict, optional): Click popup template —
              {"title": "{name}", "fields": ["name", "type"]}.
            Image overlay fields (layer_type "image"):
            - image_url (str): URL of the raster image to overlay.
            - image_bounds (list): [[south_lat, west_lon], [north_lat, east_lon]].
            Tile layer fields (layer_type "tiles"):
            - tile_url (str): XYZ tile URL template, e.g. "https://…/{z}/{x}/{y}.png".
            - tile_attribution (str, optional): Attribution shown in map control.
            - tile_min_zoom / tile_max_zoom (int, optional): Zoom range for tiles.
            Common fields (all layer types):
            - visible (bool, optional): Initial layer visibility (default true).
            - opacity (float, optional): Layer opacity 0.0–1.0.
        basemap: Base map tiles — osm (default), satellite, terrain, dark.
        center_lat: Map centre latitude (decimal degrees). Auto-detected if omitted.
        center_lon: Map centre longitude (decimal degrees). Auto-detected if omitted.
        zoom: Zoom level 1–15. Auto-calculated from feature/image extent if omitted.

    Returns:
        MapContent rendered in the interactive map view.

    Example:
        show_map(
            layers='[{"id":"cities","label":"Cities","features":{"type":"FeatureCollection",'
                   '"features":[{"type":"Feature","geometry":{"type":"Point",'
                   '"coordinates":[-0.12,51.5]},"properties":{"name":"London"}}]},'
                   '"cluster":true,"popup":{"title":"{name}"}}]',
            basemap="osm",
        )
    """
    layer_defs = parse_layer_defs(layers)
    if not layer_defs:
        raise ValueError("layers must contain at least one layer definition.")

    built_layers = [build_map_layer(ld, i) for i, ld in enumerate(layer_defs)]

    center_lat, center_lon, zoom = auto_center_zoom(layer_defs, center_lat, center_lon, zoom)

    map_center = (
        MapCenter(lat=center_lat, lon=center_lon)
        if center_lat is not None and center_lon is not None
        else None
    )

    return MapContent(
        layers=built_layers,
        center=map_center,
        zoom=zoom,
        basemap=_resolve_basemap(basemap),
        controls=_DEFAULT_CONTROLS,
    )


# ---------------------------------------------------------------------------
# Tool: show_geojson
# ---------------------------------------------------------------------------


@map_tool(
    mcp,
    "show_geojson",
    description=(
        "RECOMMENDED for simple maps — pass raw GeoJSON and get an interactive map. "
        "Accepts FeatureCollection, Feature, or bare Geometry as a JSON string. "
        "Auto-centres and auto-zooms on the features. "
        "basemap: osm (default), satellite, terrain, dark."
    ),
    read_only_hint=True,
)
async def show_geojson(
    geojson: str,
    label: str = "Features",
    basemap: str = "osm",
    fill_color: Optional[str] = None,
    stroke_color: Optional[str] = None,
    cluster: bool = False,
) -> MapContent:
    """Render raw GeoJSON as an interactive single-layer map.

    Args:
        geojson: GeoJSON string — FeatureCollection, Feature, or bare Geometry.
            Example: '{"type":"FeatureCollection","features":[...]}'
        label: Layer name shown in the map legend.
        basemap: Base map tiles — osm (default), satellite, terrain, dark.
        fill_color: Polygon / circle fill colour (hex, e.g. "#3388ff").
        stroke_color: Line / polygon stroke colour (hex).
        cluster: Cluster point markers (default false).

    Returns:
        MapContent rendered in the interactive map view.

    Example:
        show_geojson(
            geojson='{"type":"Feature","geometry":{"type":"Point",'
                    '"coordinates":[-0.12,51.5]},"properties":{"name":"London"}}',
            label="Capital Cities",
            basemap="osm",
        )
    """
    geojson_dict = parse_geojson(geojson)
    fc = ensure_feature_collection(geojson_dict)

    style_dict: dict = {}
    if fill_color:
        style_dict["fill_color"] = fill_color
        style_dict["fill_opacity"] = 0.4
    if stroke_color:
        style_dict["color"] = stroke_color

    style = build_layer_style(style_dict, LAYER_COLOURS[0] if not style_dict else None)
    cluster_config = ClusterConfig(enabled=True, radius=80) if cluster else None

    from chuk_view_schemas.map import MapLayer

    layer = MapLayer(id="geojson", label=label, features=fc, style=style, cluster=cluster_config)

    center = calculate_center(fc)
    map_center = MapCenter(lat=center[0], lon=center[1]) if center else None

    return MapContent(
        layers=[layer],
        center=map_center,
        zoom=calculate_zoom(fc),
        basemap=_resolve_basemap(basemap),
        controls=_DEFAULT_CONTROLS,
    )


# ---------------------------------------------------------------------------
# Tool: show_bbox
# ---------------------------------------------------------------------------


@map_tool(
    mcp,
    "show_bbox",
    description=(
        "Highlight a geographic bounding box as a filled polygon on an interactive map. "
        "Useful for showing an area of interest, search extent, or raster coverage. "
        "Coordinates are decimal degrees (WGS84): west, south, east, north."
    ),
    read_only_hint=True,
)
async def show_bbox(
    west: float,
    south: float,
    east: float,
    north: float,
    label: str = "Area",
    basemap: str = "osm",
    fill_color: str = "#3388ff",
) -> MapContent:
    """Display a bounding box as a highlighted polygon on a map.

    Args:
        west: Western longitude boundary (decimal degrees, WGS84).
        south: Southern latitude boundary (decimal degrees, WGS84).
        east: Eastern longitude boundary (decimal degrees, WGS84).
        north: Northern latitude boundary (decimal degrees, WGS84).
        label: Layer label shown in the map legend.
        basemap: Base map tiles — osm (default), satellite, terrain, dark.
        fill_color: Polygon fill colour (hex, default "#3388ff").

    Returns:
        MapContent with the bounding box highlighted on the map.

    Example:
        show_bbox(west=-0.5, south=51.2, east=0.3, north=51.7, label="London Area")
    """
    if west >= east:
        raise ValueError(f"west ({west}) must be less than east ({east}).")
    if south >= north:
        raise ValueError(f"south ({south}) must be less than north ({north}).")

    fc = bbox_to_feature_collection(west, south, east, north, label=label)
    style = LayerStyle(color=fill_color, weight=2, fill_color=fill_color, fill_opacity=0.2)

    from chuk_view_schemas.map import MapLayer

    layer = MapLayer(id="bbox", label=label, features=fc, style=style)

    return MapContent(
        layers=[layer],
        center=MapCenter(lat=(south + north) / 2.0, lon=(west + east) / 2.0),
        zoom=calculate_zoom_from_bbox(west, south, east, north),
        basemap=_resolve_basemap(basemap),
        controls=_DEFAULT_CONTROLS,
    )


# ---------------------------------------------------------------------------
# Tool: show_layers
# ---------------------------------------------------------------------------


@layers_tool(
    mcp,
    "show_layers",
    description=(
        "Render a simplified multi-layer map overview (no per-layer styling or popups). "
        "Lighter than show_map — use this for quick multi-dataset overviews. "
        'layers: JSON array — [{"id":"l1","label":"Layer 1","features":{...GeoJSON...}}]. '
        "Use show_map for styled, interactive layers with clustering and popups."
    ),
    read_only_hint=True,
)
async def show_layers(
    layers: str,
    title: Optional[str] = None,
    basemap: str = "osm",
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    zoom: Optional[int] = None,
) -> LayersContent:
    """Render a simplified multi-layer map.

    Args:
        layers: JSON array of layer definitions. Each object needs:
            - id (str): Unique layer ID.
            - label (str): Layer name shown in the legend.
            - features (dict | str): GeoJSON FeatureCollection, Feature, or Geometry.
            - visible (bool, optional): Initial layer visibility (default true).
            - opacity (float, optional): Layer opacity 0.0–1.0.
        title: Optional map title.
        basemap: Base map tiles — osm (default), satellite, terrain, dark.
        center_lat: Map centre latitude (auto-computed if omitted).
        center_lon: Map centre longitude (auto-computed if omitted).
        zoom: Zoom level 1–15 (auto-computed if omitted).

    Returns:
        LayersContent rendered in the layers map view.
    """
    layer_defs = parse_layer_defs(layers)
    if not layer_defs:
        raise ValueError("layers must contain at least one layer definition.")

    built_layers = [build_layers_layer(ld, i) for i, ld in enumerate(layer_defs)]

    center_lat, center_lon, zoom = auto_center_zoom(layer_defs, center_lat, center_lon, zoom)

    layers_center = (
        LayersCenter(lat=center_lat, lon=center_lon)
        if center_lat is not None and center_lon is not None
        else None
    )

    return LayersContent(
        title=title,
        center=layers_center,
        zoom=zoom,
        layers=built_layers,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Map MCP server."""
    use_stdio = True

    if len(sys.argv) > 1 and sys.argv[1] in ("http", "--http"):
        use_stdio = False
        logger.warning("Starting Chuk MCP Map Server in HTTP mode")

    if use_stdio:
        logging.getLogger("chuk_mcp_server").setLevel(logging.ERROR)
        logging.getLogger("chuk_mcp_server.core").setLevel(logging.ERROR)
        logging.getLogger("chuk_mcp_server.stdio_transport").setLevel(logging.ERROR)

    mcp.run(stdio=use_stdio)


if __name__ == "__main__":
    main()

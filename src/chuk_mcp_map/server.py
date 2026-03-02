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
from typing import Any, Optional, Union

from chuk_mcp_server import ChukMCPServer
from chuk_view_schemas.layers import LayersCenter, LayersContent
from chuk_view_schemas.map import ClusterConfig, LayerStyle, MapCenter, MapContent, MapControls
from chuk_view_schemas.chuk_mcp import layers_tool, map_tool

from .helpers import (
    LAYER_COLOURS,
    _auto_popup,
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
        "ADVANCED multi-layer map — use ONLY when you need multiple layers, image overlays, "
        "tile layers, or explicit custom styling. For single-layer maps, use show_geojson instead. "
        "layers: JSON array of layer objects. "
        'GeoJSON layer: {"id":"l1","label":"Layer","features":{...GeoJSON...},"style":{...},"cluster":true}. '
        'Image overlay: {"id":"img","layer_type":"image","label":"Thumbnail",'
        '"image_url":"https://...","image_bounds":[[south,west],[north,east]]}. '
        'Tile layer: {"id":"tiles","layer_type":"tiles","label":"Tiles",'
        '"tile_url":"https://example.com/{z}/{x}/{y}.png"}. '
        "basemap: osm | satellite | terrain | dark. "
        "center/zoom auto-computed if omitted."
    ),
    read_only_hint=True,
)
async def show_map(
    layers: Union[str, list[Any]],
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
        "RECOMMENDED for single-layer maps — pass raw GeoJSON and get an interactive map instantly. "
        "Clickable popups are auto-generated from feature properties (name, temp, conditions, etc.). "
        "Just build a GeoJSON FeatureCollection with properties and pass it as a string. "
        "Accepts FeatureCollection, Feature, or bare Geometry. "
        "CUSTOM MARKER ICONS: Set icon param for one icon on all markers, OR put an 'icon' URL in "
        "each feature's properties for per-marker icons (e.g. different icons per point). "
        "Auto-centres and auto-zooms. basemap: osm | satellite | terrain | dark."
    ),
    read_only_hint=True,
)
async def show_geojson(
    geojson: str,
    label: str = "Features",
    basemap: str = "osm",
    fill_color: Optional[str] = None,
    stroke_color: Optional[str] = None,
    icon: Optional[str] = None,
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
        icon: URL to a PNG/SVG image to use as the marker icon (replaces the
            default blue pin). Example: "https://cdn.example.com/weather/cloudy.png".
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
    if icon:
        style_dict["icon"] = icon

    style = build_layer_style(style_dict, LAYER_COLOURS[0] if not style_dict else None)
    cluster_config = ClusterConfig(enabled=True, radius=80) if cluster else None

    from chuk_view_schemas.map import MapLayer

    popup = _auto_popup(fc)
    layer = MapLayer(
        id="geojson", label=label, features=fc, style=style, cluster=cluster_config, popup=popup
    )

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
        "Highlight a bounding box on a map — pass west, south, east, north (decimal degrees WGS84). "
        "Use for areas of interest, search extents, or coverage regions."
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
        "Simple multi-layer map — no styling or popups, just multiple GeoJSON layers with toggles. "
        "Use show_map instead if you need popups, styling, or clustering. "
        'layers: JSON array — [{"id":"l1","label":"Layer 1","features":{...GeoJSON...}}].'
    ),
    read_only_hint=True,
)
async def show_layers(
    layers: Union[str, list[Any]],
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

"""Helper utilities for chuk-mcp-map.

Covers GeoJSON parsing/validation, coordinate extraction, centre and zoom
calculation, bbox polygon generation, and MapLayer / LayersLayer construction.
"""

from __future__ import annotations

import json
import logging
import math
from typing import Any

from chuk_view_schemas.layers import LayersLayer
from chuk_view_schemas.map import ClusterConfig, LayerStyle, MapLayer, PopupTemplate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default colour palette (auto-assigned to layers that have no explicit style)
# ---------------------------------------------------------------------------
LAYER_COLOURS: list[str] = [
    "#3388ff",  # blue
    "#ff6384",  # red/pink
    "#2ecc71",  # green
    "#f39c12",  # orange
    "#9b59b6",  # purple
    "#1abc9c",  # teal
    "#e74c3c",  # red
    "#34495e",  # dark grey
]


# ---------------------------------------------------------------------------
# GeoJSON parsing & normalisation
# ---------------------------------------------------------------------------


def parse_geojson(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Parse and lightly validate a GeoJSON value (string or dict)."""
    if isinstance(raw, str):
        try:
            geojson: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid GeoJSON string: {exc}") from exc
    else:
        geojson = raw

    if not isinstance(geojson, dict):
        raise ValueError("GeoJSON must be a JSON object.")
    if "type" not in geojson:
        raise ValueError("GeoJSON must have a 'type' field.")
    return geojson


def ensure_feature_collection(geojson: dict[str, Any]) -> dict[str, Any]:
    """Return a FeatureCollection, wrapping a bare Feature or Geometry if needed."""
    gtype = geojson.get("type")
    if gtype == "FeatureCollection":
        return geojson
    if gtype == "Feature":
        return {"type": "FeatureCollection", "features": [geojson]}
    if gtype in (
        "Point",
        "LineString",
        "Polygon",
        "MultiPoint",
        "MultiLineString",
        "MultiPolygon",
        "GeometryCollection",
    ):
        return {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": geojson, "properties": {}}],
        }
    raise ValueError(f"Unrecognised GeoJSON type: {gtype!r}")


# ---------------------------------------------------------------------------
# Coordinate extraction & bounding-box helpers
# ---------------------------------------------------------------------------


def _extract_coordinates(geojson: dict[str, Any]) -> list[list[float]]:
    """Recursively collect all [lon, lat] coordinate pairs from a GeoJSON object."""
    coords: list[list[float]] = []
    gtype = geojson.get("type", "")

    if gtype == "FeatureCollection":
        for feature in geojson.get("features", []):
            coords.extend(_extract_coordinates(feature))
    elif gtype == "Feature":
        geom = geojson.get("geometry")
        if geom:
            coords.extend(_extract_coordinates(geom))
    elif gtype == "Point":
        c = geojson.get("coordinates", [])
        if len(c) >= 2:
            coords.append(c[:2])
    elif gtype in ("LineString", "MultiPoint"):
        for c in geojson.get("coordinates", []):
            if len(c) >= 2:
                coords.append(c[:2])
    elif gtype in ("Polygon", "MultiLineString"):
        for ring in geojson.get("coordinates", []):
            for c in ring:
                if len(c) >= 2:
                    coords.append(c[:2])
    elif gtype == "MultiPolygon":
        for poly in geojson.get("coordinates", []):
            for ring in poly:
                for c in ring:
                    if len(c) >= 2:
                        coords.append(c[:2])
    elif gtype == "GeometryCollection":
        for geom in geojson.get("geometries", []):
            coords.extend(_extract_coordinates(geom))

    return coords


def get_bbox(geojson: dict[str, Any]) -> tuple[float, float, float, float] | None:
    """Return (west, south, east, north) bounding box, or None if no coordinates found."""
    coords = _extract_coordinates(geojson)
    if not coords:
        return None
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def calculate_center(geojson: dict[str, Any]) -> tuple[float, float] | None:
    """Return (lat, lon) centre of the GeoJSON bounding box."""
    bbox = get_bbox(geojson)
    if bbox is None:
        return None
    west, south, east, north = bbox
    return ((south + north) / 2.0, (west + east) / 2.0)


def calculate_zoom_from_bbox(west: float, south: float, east: float, north: float) -> int:
    """Estimate a sensible zoom level (1–15) from a bounding box."""
    extent = max(east - west, north - south)
    if extent <= 0:
        return 14
    zoom = round(10 - math.log2(extent))
    return max(1, min(15, zoom))


def calculate_zoom(geojson: dict[str, Any]) -> int:
    """Estimate zoom level from the extent of a GeoJSON object (default 8)."""
    bbox = get_bbox(geojson)
    if bbox is None:
        return 8
    return calculate_zoom_from_bbox(*bbox)


# ---------------------------------------------------------------------------
# Bbox → GeoJSON polygon
# ---------------------------------------------------------------------------


def bbox_to_feature_collection(
    west: float,
    south: float,
    east: float,
    north: float,
    label: str = "Area",
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection containing a single bbox Polygon."""
    props: dict[str, Any] = properties if properties is not None else {"label": label}
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [west, south],
                            [east, south],
                            [east, north],
                            [west, north],
                            [west, south],
                        ]
                    ],
                },
                "properties": props,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------


def _normalise_style_keys(raw: dict[str, Any]) -> dict[str, Any]:
    """Map camelCase style keys to Pydantic snake_case field names."""
    alias_map = {
        "fillColor": "fill_color",
        "fillOpacity": "fill_opacity",
    }
    return {alias_map.get(k, k): v for k, v in raw.items()}


def build_layer_style(
    style_dict: dict[str, Any] | None,
    default_color: str | None = None,
) -> LayerStyle | None:
    """Construct a LayerStyle, applying camelCase normalisation and optional default colour."""
    if not style_dict and not default_color:
        return None

    raw = dict(style_dict) if style_dict else {}
    normalised = _normalise_style_keys(raw)

    if default_color and "color" not in normalised:
        normalised["color"] = default_color

    try:
        return LayerStyle(**normalised)
    except (TypeError, ValueError) as exc:
        logger.warning("Invalid style, using default colour: %s", exc)
        return LayerStyle(color=default_color) if default_color else None


# ---------------------------------------------------------------------------
# Layer definition parsers
# ---------------------------------------------------------------------------


def parse_layer_defs(layers_raw: str | list[Any]) -> list[dict[str, Any]]:
    """Parse layer definitions from a JSON string or a pre-parsed list.

    Accepts either a JSON-encoded string (``'[{...}, ...]'``) or a Python
    list of dicts.  This makes the tool resilient to both string-encoded
    and directly-passed JSON arrays from LLM tool calls.
    """
    if isinstance(layers_raw, list):
        return layers_raw

    try:
        layers = json.loads(layers_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"layers must be a valid JSON array: {exc}") from exc

    if not isinstance(layers, list):
        raise ValueError("layers must be a JSON array of objects.")

    return layers


def _resolve_features(raw: Any) -> dict[str, Any]:
    """Parse features from a layer definition (string or dict) into a FeatureCollection."""
    if isinstance(raw, str):
        raw = parse_geojson(raw)
    if not isinstance(raw, dict):
        raw = {"type": "FeatureCollection", "features": []}
    return ensure_feature_collection(raw)


# ---------------------------------------------------------------------------
# Popup helpers — key filtering, ordering, formatting, title selection
# ---------------------------------------------------------------------------

# Keys excluded from auto-generated popups (case-insensitive exact match)
_EXCLUDE_EXACT: set[str] = {
    "id",
    "fid",
    "gid",
    "objectid",
    "object_id",
    "geometry_type",
    "bbox",
    "geom",
    "geometry",
    "shape",
    "ogc_fid",
    "icon",
}

# Key suffixes that trigger exclusion
_EXCLUDE_SUFFIXES: tuple[str, ...] = ("_id",)

# Priority ordering for popup fields (first match wins position)
_PRIORITY_FIELDS: list[str] = [
    "name",
    "title",
    "label",
    "description",
    "type",
    "category",
    "status",
]

# Unit suffixes detected from key names — (key_suffix, display_unit)
_UNIT_MAP: list[tuple[str, str]] = [
    ("_celsius", " °C"),
    ("_c", " °C"),
    ("_fahrenheit", " °F"),
    ("_f", " °F"),
    ("_kelvin", " K"),
    ("_km", " km"),
    ("_m", " m"),
    ("_mi", " mi"),
    ("_ft", " ft"),
    ("_percent", " %"),
    ("_pct", " %"),
    ("_kmh", " km/h"),
    ("_kph", " km/h"),
    ("_mph", " mph"),
    ("_hpa", " hPa"),
    ("_mbar", " mbar"),
    ("_mm", " mm"),
    ("_cm", " cm"),
    ("_in", " in"),
    ("_kg", " kg"),
    ("_lb", " lb"),
]


def _should_exclude_key(key: str) -> bool:
    """Return True if *key* is an internal/technical property that should be hidden."""
    if key.startswith("_"):
        return True
    lower = key.lower()
    if lower in _EXCLUDE_EXACT:
        return True
    for suffix in _EXCLUDE_SUFFIXES:
        if lower.endswith(suffix):
            return True
    return False


def _humanize_key(key: str) -> str:
    """Convert a property key to a human-readable label.

    ``wind_speed`` → ``"Wind Speed"``, ``numberOfItems`` → ``"Number Of Items"``.
    """
    import re

    # Split on underscores first
    parts = key.split("_")
    # Then split each part on camelCase boundaries
    words: list[str] = []
    for part in parts:
        words.extend(re.sub(r"([a-z])([A-Z])", r"\1 \2", part).split())
    return " ".join(w.capitalize() for w in words if w)


def _format_value(key: str, value: Any) -> str:
    """Format a property value for display, with optional unit suffix from *key*.

    Numbers are comma-formatted.  Unit suffixes are detected from the key name
    (e.g. ``temp_celsius`` → ``"12 °C"``).
    """
    if value is None:
        return ""

    lower_key = key.lower()

    # Detect unit suffix from key name
    unit = ""
    for suffix, display_unit in _UNIT_MAP:
        if lower_key.endswith(suffix):
            unit = display_unit
            break

    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}{unit}"
    if isinstance(value, float):
        # Avoid trailing zeros: 12.0 → "12", 12.5 → "12.5"
        formatted = f"{value:,.10f}".rstrip("0").rstrip(".")
        return f"{formatted}{unit}"
    return str(value)


def _order_fields(keys: list[str]) -> list[str]:
    """Reorder *keys* so priority fields appear first, preserving original order otherwise."""
    key_set = {k.lower(): k for k in keys}
    ordered: list[str] = []
    seen: set[str] = set()

    # Priority fields first
    for pf in _PRIORITY_FIELDS:
        if pf in key_set and key_set[pf] not in seen:
            ordered.append(key_set[pf])
            seen.add(key_set[pf])

    # Remaining fields in original order
    for k in keys:
        if k not in seen:
            ordered.append(k)
            seen.add(k)

    return ordered


def _pick_title(keys: list[str], seen: set[str]) -> tuple[str, list[str]]:
    """Choose a popup title template and return the keys consumed by the title.

    Returns ``(title_template, title_keys_used)``.  Prefers ``name``, then
    ``title``, then ``label``, else the first key.  When both a name key and
    a type/category key are present, produces a compound title like
    ``"{name} — {type}"``.
    """
    lower_seen = {k.lower() for k in seen}
    # Map lowercase → original
    lower_map = {k.lower(): k for k in seen}

    # Find primary title key
    primary: str | None = None
    for candidate in ("name", "title", "label"):
        if candidate in lower_seen:
            primary = lower_map[candidate]
            break
    if primary is None:
        primary = keys[0] if keys else "id"

    # Check for compound title (primary + type/category)
    secondary: str | None = None
    if primary.lower() in ("name", "title", "label"):
        for candidate in ("type", "category"):
            if candidate in lower_seen and lower_map[candidate] != primary:
                secondary = lower_map[candidate]
                break

    if secondary:
        title = "{" + primary + "} — {" + secondary + "}"
        return title, [primary, secondary]

    return "{" + primary + "}", [primary]


def _auto_popup(fc: dict[str, Any]) -> PopupTemplate | None:
    """Build a PopupTemplate from the union of all feature property keys.

    Scans all features for property keys, filters out internal/technical keys,
    orders fields by priority, picks a smart title (with optional compound
    ``"name — type"`` format), and returns remaining keys as popup fields.
    """
    all_keys: list[str] = []
    seen: set[str] = set()
    for feat in fc.get("features", []):
        for k in (feat.get("properties") or {}).keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    # Filter out internal/technical keys
    display_keys = [k for k in all_keys if not _should_exclude_key(k)]
    if not display_keys:
        return None

    # Order by priority
    ordered = _order_fields(display_keys)
    display_seen = set(display_keys)

    # Pick title
    title, title_keys = _pick_title(ordered, display_seen)

    # Fields = everything except title keys
    title_set = set(title_keys)
    fields = [k for k in ordered if k not in title_set]

    return PopupTemplate(title=title, fields=fields if fields else None)


def build_map_layer(layer_def: dict[str, Any], index: int) -> MapLayer:
    """Build a MapLayer from a layer definition dict."""
    layer_id: str = layer_def.get("id") or f"layer-{index}"
    label: str = layer_def.get("label") or f"Layer {index + 1}"
    layer_type = layer_def.get("layer_type")

    # --- Image overlay ---
    if layer_type == "image":
        return MapLayer(
            id=layer_id,
            label=label,
            layer_type="image",
            visible=layer_def.get("visible"),
            opacity=layer_def.get("opacity"),
            image_url=layer_def.get("image_url"),
            image_bounds=layer_def.get("image_bounds"),
        )

    # --- XYZ tile layer ---
    if layer_type == "tiles":
        return MapLayer(
            id=layer_id,
            label=label,
            layer_type="tiles",
            visible=layer_def.get("visible"),
            opacity=layer_def.get("opacity"),
            tile_url=layer_def.get("tile_url"),
            tile_attribution=layer_def.get("tile_attribution"),
            tile_min_zoom=layer_def.get("tile_min_zoom"),
            tile_max_zoom=layer_def.get("tile_max_zoom"),
        )

    # --- GeoJSON (default) ---
    features = _resolve_features(layer_def.get("features", {}))

    default_color = LAYER_COLOURS[index % len(LAYER_COLOURS)]
    style = build_layer_style(layer_def.get("style"), default_color)

    # Cluster
    cluster: ClusterConfig | None = None
    cluster_raw = layer_def.get("cluster")
    if cluster_raw is True:
        cluster = ClusterConfig(enabled=True, radius=80)
    elif isinstance(cluster_raw, dict):
        try:
            cluster = ClusterConfig(**cluster_raw)
        except (TypeError, ValueError) as exc:
            logger.warning("Invalid cluster config, using defaults: %s", exc)
            cluster = ClusterConfig(enabled=True, radius=80)

    # Popup — explicit template, or auto-generate from feature properties
    popup: PopupTemplate | None = None
    popup_raw = layer_def.get("popup")
    if isinstance(popup_raw, dict):
        try:
            popup = PopupTemplate(**popup_raw)
        except (TypeError, ValueError) as exc:
            logger.warning("Invalid popup template, skipping: %s", exc)

    if popup is None:
        popup = _auto_popup(features)

    return MapLayer(
        id=layer_id,
        label=label,
        visible=layer_def.get("visible"),
        opacity=layer_def.get("opacity"),
        features=features,
        style=style,
        cluster=cluster,
        popup=popup,
    )


def build_layers_layer(layer_def: dict[str, Any], index: int) -> LayersLayer:
    """Build a LayersLayer (simplified, style-free) from a layer definition dict."""
    layer_id: str = layer_def.get("id") or f"layer-{index}"
    label: str = layer_def.get("label") or f"Layer {index + 1}"
    features = _resolve_features(layer_def.get("features", {}))

    return LayersLayer(
        id=layer_id,
        label=label,
        visible=layer_def.get("visible"),
        opacity=layer_def.get("opacity"),
        features=features,
    )


# ---------------------------------------------------------------------------
# Shared: auto-compute centre + zoom from a list of layer defs
# ---------------------------------------------------------------------------


def auto_center_zoom(
    layer_defs: list[dict[str, Any]],
    center_lat: float | None,
    center_lon: float | None,
    zoom: int | None,
) -> tuple[float | None, float | None, int | None]:
    """Derive missing centre/zoom from the union of all layer features or image bounds."""
    if center_lat is not None and center_lon is not None and zoom is not None:
        return center_lat, center_lon, zoom

    all_features: list[dict[str, Any]] = []
    image_bounds_list: list[list[list[float]]] = []

    for ld in layer_defs:
        layer_type = ld.get("layer_type")
        if layer_type == "image":
            bounds = ld.get("image_bounds")
            if bounds and len(bounds) == 2:
                image_bounds_list.append(bounds)
            continue
        if layer_type == "tiles":
            continue
        features_raw = ld.get("features", {})
        try:
            fc = _resolve_features(features_raw)
            all_features.extend(fc.get("features", []))
        except (ValueError, TypeError) as exc:
            logger.warning("Skipping layer with bad features: %s", exc)
            continue

    combined: dict[str, Any] = {"type": "FeatureCollection", "features": all_features}

    if center_lat is None or center_lon is None:
        center = calculate_center(combined)
        if center:
            center_lat = center_lat if center_lat is not None else center[0]
            center_lon = center_lon if center_lon is not None else center[1]
        elif image_bounds_list:
            # [[south, west], [north, east]] per Leaflet convention
            south = min(b[0][0] for b in image_bounds_list)
            west = min(b[0][1] for b in image_bounds_list)
            north = max(b[1][0] for b in image_bounds_list)
            east = max(b[1][1] for b in image_bounds_list)
            center_lat = (south + north) / 2.0
            center_lon = (west + east) / 2.0

    if zoom is None:
        zoom = calculate_zoom(combined)
        if zoom == 8 and image_bounds_list and not all_features:
            south = min(b[0][0] for b in image_bounds_list)
            west = min(b[0][1] for b in image_bounds_list)
            north = max(b[1][0] for b in image_bounds_list)
            east = max(b[1][1] for b in image_bounds_list)
            zoom = calculate_zoom_from_bbox(west, south, east, north)

    return center_lat, center_lon, zoom

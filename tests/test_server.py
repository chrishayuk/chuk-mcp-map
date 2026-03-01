"""Tests for chuk-mcp-map server tools and helpers."""

from __future__ import annotations

import json
import sys
import os
from unittest.mock import patch

import pytest

# Make sure the source package is importable when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from chuk_mcp_map.helpers import (
    LAYER_COLOURS,
    _auto_popup,
    _extract_coordinates,
    _format_value,
    _humanize_key,
    _order_fields,
    _pick_title,
    _resolve_features,
    _should_exclude_key,
    auto_center_zoom,
    bbox_to_feature_collection,
    build_layer_style,
    build_layers_layer,
    build_map_layer,
    calculate_center,
    calculate_zoom,
    calculate_zoom_from_bbox,
    ensure_feature_collection,
    get_bbox,
    parse_geojson,
    parse_layer_defs,
)
from chuk_mcp_map.server import show_bbox, show_geojson, show_layers, show_map

# ---------------------------------------------------------------------------
# Fixtures / shared GeoJSON
# ---------------------------------------------------------------------------

POINT_FEATURE = {
    "type": "Feature",
    "geometry": {"type": "Point", "coordinates": [-0.12, 51.5]},
    "properties": {"name": "London"},
}

POLYGON_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-1, 50], [1, 50], [1, 52], [-1, 52], [-1, 50]]],
    },
    "properties": {"name": "UK bbox"},
}

FEATURE_COLLECTION = {
    "type": "FeatureCollection",
    "features": [POINT_FEATURE, POLYGON_FEATURE],
}


# ===========================================================================
# Helper: parse_geojson
# ===========================================================================


class TestParseGeojson:
    def test_parses_dict(self):
        result = parse_geojson(POINT_FEATURE)
        assert result["type"] == "Feature"

    def test_parses_json_string(self):
        result = parse_geojson(json.dumps(POINT_FEATURE))
        assert result["type"] == "Feature"

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid GeoJSON"):
            parse_geojson("{bad json}")

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="'type'"):
            parse_geojson({"coordinates": [0, 0]})

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="JSON object"):
            parse_geojson("[1, 2, 3]")


# ===========================================================================
# Helper: ensure_feature_collection
# ===========================================================================


class TestEnsureFeatureCollection:
    def test_feature_collection_passthrough(self):
        result = ensure_feature_collection(FEATURE_COLLECTION)
        assert result["type"] == "FeatureCollection"
        assert len(result["features"]) == 2

    def test_wraps_feature(self):
        result = ensure_feature_collection(POINT_FEATURE)
        assert result["type"] == "FeatureCollection"
        assert result["features"][0] == POINT_FEATURE

    def test_wraps_bare_geometry(self):
        geom = {"type": "Point", "coordinates": [0, 0]}
        result = ensure_feature_collection(geom)
        assert result["type"] == "FeatureCollection"
        assert result["features"][0]["geometry"] == geom

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unrecognised"):
            ensure_feature_collection({"type": "UnknownType"})


# ===========================================================================
# Helper: get_bbox / calculate_center / calculate_zoom
# ===========================================================================


class TestBboxAndCenter:
    def test_get_bbox_point(self):
        fc = ensure_feature_collection(POINT_FEATURE)
        bbox = get_bbox(fc)
        assert bbox == (-0.12, 51.5, -0.12, 51.5)

    def test_get_bbox_polygon(self):
        fc = ensure_feature_collection(POLYGON_FEATURE)
        bbox = get_bbox(fc)
        assert bbox == (-1.0, 50.0, 1.0, 52.0)

    def test_get_bbox_empty_returns_none(self):
        assert get_bbox({"type": "FeatureCollection", "features": []}) is None

    def test_calculate_center_point(self):
        fc = ensure_feature_collection(POINT_FEATURE)
        center = calculate_center(fc)
        assert center == pytest.approx((51.5, -0.12))

    def test_calculate_center_polygon(self):
        fc = ensure_feature_collection(POLYGON_FEATURE)
        center = calculate_center(fc)
        assert center == pytest.approx((51.0, 0.0))

    def test_calculate_center_empty_returns_none(self):
        assert calculate_center({"type": "FeatureCollection", "features": []}) is None


class TestZoom:
    def test_small_extent_high_zoom(self):
        zoom = calculate_zoom_from_bbox(-0.01, 51.49, 0.01, 51.51)
        assert zoom >= 10

    def test_large_extent_low_zoom(self):
        zoom = calculate_zoom_from_bbox(-180, -90, 180, 90)
        assert zoom <= 3

    def test_medium_extent(self):
        zoom = calculate_zoom_from_bbox(-1, 50, 1, 52)
        assert 5 <= zoom <= 9

    def test_zero_extent_returns_14(self):
        zoom = calculate_zoom_from_bbox(0, 0, 0, 0)
        assert zoom == 14

    def test_calculate_zoom_empty_returns_8(self):
        assert calculate_zoom({"type": "FeatureCollection", "features": []}) == 8


# ===========================================================================
# Helper: bbox_to_feature_collection
# ===========================================================================


class TestBboxToFeatureCollection:
    def test_creates_polygon(self):
        fc = bbox_to_feature_collection(-1, 50, 1, 52, label="Test")
        assert fc["type"] == "FeatureCollection"
        assert len(fc["features"]) == 1
        geom = fc["features"][0]["geometry"]
        assert geom["type"] == "Polygon"
        # First and last coordinate should match (closed ring)
        ring = geom["coordinates"][0]
        assert ring[0] == ring[-1]

    def test_label_in_properties(self):
        fc = bbox_to_feature_collection(-1, 50, 1, 52, label="MyArea")
        assert fc["features"][0]["properties"]["label"] == "MyArea"

    def test_custom_properties(self):
        fc = bbox_to_feature_collection(-1, 50, 1, 52, properties={"key": "val"})
        assert fc["features"][0]["properties"] == {"key": "val"}


# ===========================================================================
# Helper: build_layer_style
# ===========================================================================


class TestBuildLayerStyle:
    def test_none_input_with_default(self):
        style = build_layer_style(None, default_color="#ff0000")
        assert style is not None
        assert style.color == "#ff0000"

    def test_both_none_returns_none(self):
        assert build_layer_style(None, None) is None

    def test_camel_case_keys_normalised(self):
        style = build_layer_style({"fillColor": "#3388ff", "fillOpacity": 0.4})
        assert style is not None
        assert style.fill_color == "#3388ff"
        assert style.fill_opacity == pytest.approx(0.4)

    def test_snake_case_keys_accepted(self):
        style = build_layer_style({"fill_color": "#3388ff"})
        assert style is not None
        assert style.fill_color == "#3388ff"

    def test_default_color_not_overridden_when_color_present(self):
        style = build_layer_style({"color": "#ff0000"}, default_color="#0000ff")
        assert style.color == "#ff0000"


# ===========================================================================
# Helper: parse_layer_defs
# ===========================================================================


class TestParseLayerDefs:
    def test_valid_array(self):
        raw = json.dumps([{"id": "a", "label": "A", "features": FEATURE_COLLECTION}])
        defs = parse_layer_defs(raw)
        assert len(defs) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="valid JSON array"):
            parse_layer_defs("{not an array}")

    def test_non_array_raises(self):
        with pytest.raises(ValueError, match="JSON array"):
            parse_layer_defs('{"id":"a"}')


# ===========================================================================
# Helper: build_map_layer
# ===========================================================================


class TestBuildMapLayer:
    def _layer_def(self, **kwargs):
        base = {"id": "l1", "label": "Layer 1", "features": FEATURE_COLLECTION}
        base.update(kwargs)
        return base

    def test_basic_layer(self):
        layer = build_map_layer(self._layer_def(), 0)
        assert layer.id == "l1"
        assert layer.label == "Layer 1"
        assert layer.features["type"] == "FeatureCollection"

    def test_auto_id_and_label(self):
        layer = build_map_layer({"features": FEATURE_COLLECTION}, 2)
        assert layer.id == "layer-2"
        assert layer.label == "Layer 3"

    def test_default_colour_assigned(self):
        layer = build_map_layer(self._layer_def(), 0)
        assert layer.style is not None
        assert layer.style.color == LAYER_COLOURS[0]

    def test_cluster_true(self):
        layer = build_map_layer(self._layer_def(cluster=True), 0)
        assert layer.cluster is not None
        assert layer.cluster.enabled is True

    def test_cluster_dict(self):
        layer = build_map_layer(self._layer_def(cluster={"enabled": True, "radius": 50}), 0)
        assert layer.cluster.radius == 50

    def test_popup_built(self):
        layer = build_map_layer(self._layer_def(popup={"title": "{name}", "fields": ["name"]}), 0)
        assert layer.popup is not None
        assert layer.popup.title == "{name}"

    def test_features_as_string(self):
        layer = build_map_layer(
            {"id": "x", "label": "X", "features": json.dumps(FEATURE_COLLECTION)}, 0
        )
        assert layer.features["type"] == "FeatureCollection"

    def test_colour_cycles(self):
        n = len(LAYER_COLOURS)
        layer = build_map_layer(self._layer_def(), n)
        assert layer.style.color == LAYER_COLOURS[0]

    def test_image_layer_type(self):
        layer_def = {
            "id": "img1",
            "label": "Thumbnail",
            "layer_type": "image",
            "image_url": "https://example.com/thumb.jpg",
            "image_bounds": [[51.85, 0.85], [51.93, 0.95]],
            "opacity": 0.9,
            "visible": False,
        }
        layer = build_map_layer(layer_def, 0)
        assert layer.id == "img1"
        assert layer.layer_type == "image"
        assert layer.image_url == "https://example.com/thumb.jpg"
        assert layer.image_bounds == [[51.85, 0.85], [51.93, 0.95]]
        assert layer.opacity == pytest.approx(0.9)
        assert layer.visible is False
        assert layer.features is None
        assert layer.style is None

    def test_image_layer_no_features_required(self):
        layer_def = {
            "layer_type": "image",
            "image_url": "https://example.com/img.png",
            "image_bounds": [[50.0, -1.0], [52.0, 1.0]],
        }
        layer = build_map_layer(layer_def, 1)
        assert layer.layer_type == "image"
        assert layer.features is None

    def test_tile_layer_type(self):
        layer_def = {
            "id": "topo",
            "label": "USGS Topo",
            "layer_type": "tiles",
            "tile_url": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
            "tile_attribution": "USGS The National Map",
            "tile_max_zoom": 16,
            "opacity": 0.7,
        }
        layer = build_map_layer(layer_def, 0)
        assert layer.layer_type == "tiles"
        assert "USGSTopo" in layer.tile_url
        assert layer.tile_attribution == "USGS The National Map"
        assert layer.tile_max_zoom == 16
        assert layer.opacity == pytest.approx(0.7)
        assert layer.features is None
        assert layer.style is None

    def test_tile_layer_minimal(self):
        layer_def = {
            "layer_type": "tiles",
            "tile_url": "https://example.com/{z}/{x}/{y}.png",
        }
        layer = build_map_layer(layer_def, 2)
        assert layer.layer_type == "tiles"
        assert layer.tile_url == "https://example.com/{z}/{x}/{y}.png"
        assert layer.tile_attribution is None


# ===========================================================================
# Helper: build_layers_layer
# ===========================================================================


class TestBuildLayersLayer:
    def test_basic(self):
        layer = build_layers_layer({"id": "l1", "label": "L1", "features": FEATURE_COLLECTION}, 0)
        assert layer.id == "l1"
        assert layer.label == "L1"

    def test_no_style_field(self):
        layer = build_layers_layer({"features": FEATURE_COLLECTION}, 1)
        assert not hasattr(layer, "style")


# ===========================================================================
# Helper: auto_center_zoom
# ===========================================================================


class TestAutoCenterZoom:
    def _layer_defs(self):
        return [{"id": "l1", "label": "L1", "features": FEATURE_COLLECTION}]

    def test_all_provided(self):
        lat, lon, z = auto_center_zoom(self._layer_defs(), 10.0, 20.0, 7)
        assert lat == 10.0
        assert lon == 20.0
        assert z == 7

    def test_auto_computed(self):
        lat, lon, z = auto_center_zoom(self._layer_defs(), None, None, None)
        assert lat is not None
        assert lon is not None
        assert z is not None

    def test_partial_center_filled(self):
        lat, lon, z = auto_center_zoom(self._layer_defs(), None, None, 8)
        assert lat is not None
        assert lon is not None
        assert z == 8

    def test_image_only_layers_use_bounds(self):
        # image_bounds [[south, west], [north, east]]
        image_defs = [
            {
                "layer_type": "image",
                "image_url": "https://example.com/img.jpg",
                "image_bounds": [[51.85, 0.85], [51.93, 0.95]],
            }
        ]
        lat, lon, z = auto_center_zoom(image_defs, None, None, None)
        assert lat == pytest.approx((51.85 + 51.93) / 2)
        assert lon == pytest.approx((0.85 + 0.95) / 2)
        assert z is not None

    def test_tile_only_layers_no_center(self):
        tile_defs = [{"layer_type": "tiles", "tile_url": "https://example.com/{z}/{x}/{y}.png"}]
        lat, lon, z = auto_center_zoom(tile_defs, None, None, None)
        # No features or image bounds — center remains None, zoom defaults
        assert lat is None
        assert lon is None


# ===========================================================================
# Tool: show_map
# ===========================================================================


class TestShowMap:
    def _layers_json(self, **kwargs):
        base = {"id": "l1", "label": "Sites", "features": FEATURE_COLLECTION}
        base.update(kwargs)
        return json.dumps([base])

    @pytest.mark.asyncio
    async def test_basic(self):
        result = await show_map(layers=self._layers_json())
        assert result.type == "map"
        assert len(result.layers) == 1

    @pytest.mark.asyncio
    async def test_explicit_center_zoom(self):
        result = await show_map(
            layers=self._layers_json(), center_lat=51.5, center_lon=-0.12, zoom=10
        )
        assert result.center.lat == pytest.approx(51.5)
        assert result.zoom == 10

    @pytest.mark.asyncio
    async def test_basemap_satellite(self):
        result = await show_map(layers=self._layers_json(), basemap="satellite")
        assert result.basemap == "satellite"

    @pytest.mark.asyncio
    async def test_invalid_basemap_defaults_to_osm(self):
        result = await show_map(layers=self._layers_json(), basemap="bogus")
        assert result.basemap == "osm"

    @pytest.mark.asyncio
    async def test_empty_layers_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            await show_map(layers="[]")

    @pytest.mark.asyncio
    async def test_multiple_layers(self):
        two = json.dumps(
            [
                {"id": "a", "label": "A", "features": FEATURE_COLLECTION},
                {"id": "b", "label": "B", "features": FEATURE_COLLECTION},
            ]
        )
        result = await show_map(layers=two)
        assert len(result.layers) == 2

    @pytest.mark.asyncio
    async def test_with_clustering(self):
        result = await show_map(layers=self._layers_json(cluster=True))
        assert result.layers[0].cluster is not None
        assert result.layers[0].cluster.enabled is True

    @pytest.mark.asyncio
    async def test_with_popup(self):
        result = await show_map(
            layers=self._layers_json(popup={"title": "{name}", "fields": ["name"]})
        )
        assert result.layers[0].popup is not None

    @pytest.mark.asyncio
    async def test_controls_present(self):
        result = await show_map(layers=self._layers_json())
        assert result.controls is not None
        assert result.controls.zoom is True

    @pytest.mark.asyncio
    async def test_terrain_basemap(self):
        result = await show_map(layers=self._layers_json(), basemap="terrain")
        assert result.basemap == "terrain"

    @pytest.mark.asyncio
    async def test_dark_basemap(self):
        result = await show_map(layers=self._layers_json(), basemap="dark")
        assert result.basemap == "dark"

    @pytest.mark.asyncio
    async def test_image_overlay_layer(self):
        layers_json = json.dumps(
            [
                {
                    "id": "thumb",
                    "label": "Satellite thumbnail",
                    "layer_type": "image",
                    "image_url": "https://example.com/thumb.jpg",
                    "image_bounds": [[51.85, 0.85], [51.93, 0.95]],
                    "opacity": 0.9,
                    "visible": False,
                }
            ]
        )
        result = await show_map(layers=layers_json, basemap="satellite")
        assert result.basemap == "satellite"
        assert len(result.layers) == 1
        layer = result.layers[0]
        assert layer.layer_type == "image"
        assert layer.image_url == "https://example.com/thumb.jpg"
        assert layer.image_bounds == [[51.85, 0.85], [51.93, 0.95]]
        assert layer.visible is False

    @pytest.mark.asyncio
    async def test_tile_overlay_layer(self):
        layers_json = json.dumps(
            [
                {
                    "id": "usgs_topo",
                    "label": "USGS Topo",
                    "layer_type": "tiles",
                    "tile_url": "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
                    "tile_attribution": "USGS The National Map",
                    "tile_max_zoom": 16,
                    "opacity": 0.6,
                    "visible": False,
                }
            ]
        )
        result = await show_map(
            layers=layers_json, basemap="osm", center_lat=40.712, center_lon=-74.006, zoom=11
        )
        assert len(result.layers) == 1
        layer = result.layers[0]
        assert layer.layer_type == "tiles"
        assert "USGSTopo" in layer.tile_url
        assert layer.tile_max_zoom == 16

    @pytest.mark.asyncio
    async def test_mixed_geojson_and_image_layers(self):
        layers_json = json.dumps(
            [
                {
                    "id": "footprints",
                    "label": "Scene footprints",
                    "features": FEATURE_COLLECTION,
                },
                {
                    "id": "thumb",
                    "label": "Thumbnail",
                    "layer_type": "image",
                    "image_url": "https://example.com/thumb.jpg",
                    "image_bounds": [[51.85, 0.85], [51.93, 0.95]],
                    "visible": False,
                },
            ]
        )
        result = await show_map(layers=layers_json)
        assert len(result.layers) == 2
        types = {la.id: la.layer_type for la in result.layers}
        assert types["footprints"] is None  # default geojson
        assert types["thumb"] == "image"


# ===========================================================================
# Tool: show_geojson
# ===========================================================================


class TestShowGeojson:
    @pytest.mark.asyncio
    async def test_feature_collection(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION))
        assert result.type == "map"
        assert len(result.layers) == 1
        assert result.layers[0].id == "geojson"

    @pytest.mark.asyncio
    async def test_bare_feature(self):
        result = await show_geojson(geojson=json.dumps(POINT_FEATURE))
        assert result.type == "map"

    @pytest.mark.asyncio
    async def test_bare_geometry(self):
        geom = {"type": "Point", "coordinates": [0, 0]}
        result = await show_geojson(geojson=json.dumps(geom))
        assert result.type == "map"

    @pytest.mark.asyncio
    async def test_custom_label(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION), label="My Layer")
        assert result.layers[0].label == "My Layer"

    @pytest.mark.asyncio
    async def test_fill_color_applied(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION), fill_color="#ff0000")
        assert result.layers[0].style.fill_color == "#ff0000"

    @pytest.mark.asyncio
    async def test_stroke_color_applied(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION), stroke_color="#00ff00")
        assert result.layers[0].style.color == "#00ff00"

    @pytest.mark.asyncio
    async def test_clustering_enabled(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION), cluster=True)
        assert result.layers[0].cluster is not None
        assert result.layers[0].cluster.enabled is True

    @pytest.mark.asyncio
    async def test_no_clustering_by_default(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION))
        assert result.layers[0].cluster is None

    @pytest.mark.asyncio
    async def test_auto_center_set(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION))
        assert result.center is not None

    @pytest.mark.asyncio
    async def test_basemap_satellite(self):
        result = await show_geojson(geojson=json.dumps(FEATURE_COLLECTION), basemap="satellite")
        assert result.basemap == "satellite"

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            await show_geojson(geojson="{bad}")


# ===========================================================================
# Tool: show_bbox
# ===========================================================================


class TestShowBbox:
    @pytest.mark.asyncio
    async def test_basic_bbox(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52)
        assert result.type == "map"
        assert len(result.layers) == 1

    @pytest.mark.asyncio
    async def test_layer_label(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52, label="England")
        assert result.layers[0].label == "England"

    @pytest.mark.asyncio
    async def test_center_calculated(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52)
        assert result.center.lat == pytest.approx(51.0)
        assert result.center.lon == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_fill_color(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52, fill_color="#ff0000")
        assert result.layers[0].style.fill_color == "#ff0000"

    @pytest.mark.asyncio
    async def test_west_ge_east_raises(self):
        with pytest.raises(ValueError, match="west"):
            await show_bbox(west=1, south=50, east=-1, north=52)

    @pytest.mark.asyncio
    async def test_south_ge_north_raises(self):
        with pytest.raises(ValueError, match="south"):
            await show_bbox(west=-1, south=52, east=1, north=50)

    @pytest.mark.asyncio
    async def test_basemap_terrain(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52, basemap="terrain")
        assert result.basemap == "terrain"

    @pytest.mark.asyncio
    async def test_default_fill_color(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52)
        assert result.layers[0].style.fill_color == "#3388ff"

    @pytest.mark.asyncio
    async def test_zoom_reasonable(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52)
        assert 1 <= result.zoom <= 15

    @pytest.mark.asyncio
    async def test_controls_present(self):
        result = await show_bbox(west=-1, south=50, east=1, north=52)
        assert result.controls is not None


# ===========================================================================
# Tool: show_layers
# ===========================================================================


class TestShowLayers:
    def _layers_json(self):
        return json.dumps(
            [
                {"id": "a", "label": "A", "features": FEATURE_COLLECTION},
                {"id": "b", "label": "B", "features": FEATURE_COLLECTION},
            ]
        )

    @pytest.mark.asyncio
    async def test_basic(self):
        result = await show_layers(layers=self._layers_json())
        assert result.type == "layers"
        assert len(result.layers) == 2

    @pytest.mark.asyncio
    async def test_title(self):
        result = await show_layers(layers=self._layers_json(), title="Overview")
        assert result.title == "Overview"

    @pytest.mark.asyncio
    async def test_no_title_by_default(self):
        result = await show_layers(layers=self._layers_json())
        assert result.title is None

    @pytest.mark.asyncio
    async def test_explicit_center_zoom(self):
        result = await show_layers(
            layers=self._layers_json(), center_lat=51.5, center_lon=-0.1, zoom=9
        )
        assert result.center.lat == pytest.approx(51.5)
        assert result.zoom == 9

    @pytest.mark.asyncio
    async def test_auto_center_computed(self):
        result = await show_layers(layers=self._layers_json())
        assert result.center is not None
        assert result.zoom is not None

    @pytest.mark.asyncio
    async def test_empty_layers_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            await show_layers(layers="[]")

    @pytest.mark.asyncio
    async def test_single_layer(self):
        single = json.dumps([{"id": "x", "label": "X", "features": FEATURE_COLLECTION}])
        result = await show_layers(layers=single)
        assert len(result.layers) == 1

    @pytest.mark.asyncio
    async def test_layer_ids_preserved(self):
        result = await show_layers(layers=self._layers_json())
        ids = [layer.id for layer in result.layers]
        assert "a" in ids
        assert "b" in ids

    @pytest.mark.asyncio
    async def test_features_in_each_layer(self):
        result = await show_layers(layers=self._layers_json())
        for layer in result.layers:
            assert layer.features["type"] == "FeatureCollection"


# ===========================================================================
# Helper: _extract_coordinates — geometry types
# ===========================================================================


class TestExtractCoordinates:
    def test_linestring(self):
        geom = {"type": "LineString", "coordinates": [[0, 1], [2, 3], [4, 5]]}
        coords = _extract_coordinates(geom)
        assert len(coords) == 3
        assert coords[0] == [0, 1]

    def test_multipoint(self):
        geom = {"type": "MultiPoint", "coordinates": [[10, 20], [30, 40]]}
        coords = _extract_coordinates(geom)
        assert len(coords) == 2

    def test_multilinestring(self):
        geom = {
            "type": "MultiLineString",
            "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]],
        }
        coords = _extract_coordinates(geom)
        assert len(coords) == 4

    def test_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
            ],
        }
        coords = _extract_coordinates(geom)
        assert len(coords) == 10

    def test_geometry_collection(self):
        geom = {
            "type": "GeometryCollection",
            "geometries": [
                {"type": "Point", "coordinates": [0, 0]},
                {"type": "Point", "coordinates": [1, 1]},
            ],
        }
        coords = _extract_coordinates(geom)
        assert len(coords) == 2


# ===========================================================================
# Helper: _resolve_features edge cases
# ===========================================================================


class TestResolveFeatures:
    def test_non_dict_input(self):
        result = _resolve_features(12345)
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []


# ===========================================================================
# Helper: build_layer_style fallback
# ===========================================================================


class TestBuildLayerStyleFallback:
    def test_invalid_style_key_falls_back(self):
        style = build_layer_style({"not_a_real_field": "bad"}, default_color="#ff0000")
        assert style is not None
        assert style.color == "#ff0000"


# ===========================================================================
# Helper: build_map_layer — error branches
# ===========================================================================


class TestBuildMapLayerErrors:
    def test_invalid_cluster_dict_falls_back(self):
        layer_def = {
            "id": "x",
            "label": "X",
            "features": FEATURE_COLLECTION,
            "cluster": {"not_a_valid_key": "bad"},
        }
        layer = build_map_layer(layer_def, 0)
        assert layer.cluster is not None
        assert layer.cluster.enabled is True
        assert layer.cluster.radius == 80

    def test_invalid_popup_dict_falls_back_to_auto(self):
        layer_def = {
            "id": "x",
            "label": "X",
            "features": FEATURE_COLLECTION,
            "popup": {"not_a_valid_key": "bad"},
        }
        layer = build_map_layer(layer_def, 0)
        # Invalid explicit popup is skipped, auto-popup takes over from properties
        assert layer.popup is not None
        assert layer.popup.title == "{name}"


# ===========================================================================
# Helper: _auto_popup
# ===========================================================================


class TestAutoPopup:
    def test_generates_popup_from_properties(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "London", "temp": "12°C", "wind": "15 km/h"},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup is not None
        assert popup.title == "{name}"
        # name consumed by title, remaining fields listed
        assert "temp" in popup.fields
        assert "wind" in popup.fields
        assert "name" not in popup.fields

    def test_prefers_name_as_title(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"city_code": "PAR", "name": "Paris", "temp": "10°C"},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup.title == "{name}"

    def test_falls_back_to_title_key(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"title": "Site A", "value": 42},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup.title == "{title}"

    def test_falls_back_to_label_key(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"label": "Zone X", "area": 100},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup.title == "{label}"

    def test_falls_back_to_first_key(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"code": "ABC", "value": 99},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup.title == "{code}"

    def test_empty_properties_returns_none(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                }
            ],
        }
        assert _auto_popup(fc) is None

    def test_no_features_returns_none(self):
        fc = {"type": "FeatureCollection", "features": []}
        assert _auto_popup(fc) is None

    def test_unions_keys_across_features(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "A", "temp": "5°C"},
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [1, 1]},
                    "properties": {"name": "B", "humidity": "80%"},
                },
            ],
        }
        popup = _auto_popup(fc)
        # name consumed by title, remaining fields listed
        assert set(popup.fields) == {"temp", "humidity"}


class TestBuildMapLayerAutoPopup:
    def test_auto_popup_when_no_popup_specified(self):
        layer_def = {"id": "x", "label": "X", "features": FEATURE_COLLECTION}
        layer = build_map_layer(layer_def, 0)
        # FEATURE_COLLECTION has properties with "name" key
        assert layer.popup is not None
        assert layer.popup.title == "{name}"

    def test_explicit_popup_not_overridden(self):
        layer_def = {
            "id": "x",
            "label": "X",
            "features": FEATURE_COLLECTION,
            "popup": {"title": "Custom: {name}", "fields": ["name"]},
        }
        layer = build_map_layer(layer_def, 0)
        assert layer.popup.title == "Custom: {name}"

    def test_no_popup_for_empty_properties(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                }
            ],
        }
        layer_def = {"id": "x", "label": "X", "features": fc}
        layer = build_map_layer(layer_def, 0)
        assert layer.popup is None


# ===========================================================================
# Helper: auto_center_zoom — bad features in layer defs
# ===========================================================================


class TestAutoCenterZoomErrors:
    def test_bad_features_skipped(self):
        layer_defs = [
            {"id": "bad", "label": "Bad", "features": "not valid json at all"},
            {"id": "good", "label": "Good", "features": FEATURE_COLLECTION},
        ]
        lat, lon, z = auto_center_zoom(layer_defs, None, None, None)
        assert lat is not None
        assert lon is not None
        assert z is not None


# ===========================================================================
# Tool: main entry point
# ===========================================================================


class TestMain:
    def test_stdio_mode(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["chuk-mcp-map"])
        with patch("chuk_mcp_map.server.mcp") as mock_mcp:
            from chuk_mcp_map.server import main

            main()
            mock_mcp.run.assert_called_once_with(stdio=True)

    def test_http_mode(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["chuk-mcp-map", "http"])
        with patch("chuk_mcp_map.server.mcp") as mock_mcp:
            from chuk_mcp_map.server import main

            main()
            mock_mcp.run.assert_called_once_with(stdio=False)

    def test_http_flag_mode(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["chuk-mcp-map", "--http"])
        with patch("chuk_mcp_map.server.mcp") as mock_mcp:
            from chuk_mcp_map.server import main

            main()
            mock_mcp.run.assert_called_once_with(stdio=False)


# ===========================================================================
# Phase 1.1: Popup helpers
# ===========================================================================


class TestShouldExcludeKey:
    """Tests for _should_exclude_key — filtering internal/technical properties."""

    def test_underscore_prefix_excluded(self):
        assert _should_exclude_key("_id") is True
        assert _should_exclude_key("_internal") is True

    def test_exact_match_excluded(self):
        assert _should_exclude_key("id") is True
        assert _should_exclude_key("fid") is True
        assert _should_exclude_key("gid") is True
        assert _should_exclude_key("objectid") is True
        assert _should_exclude_key("geometry_type") is True
        assert _should_exclude_key("bbox") is True
        assert _should_exclude_key("geom") is True
        assert _should_exclude_key("ogc_fid") is True

    def test_case_insensitive(self):
        assert _should_exclude_key("OBJECTID") is True
        assert _should_exclude_key("ObjectId") is True
        assert _should_exclude_key("FID") is True

    def test_suffix_id_excluded(self):
        assert _should_exclude_key("user_id") is True
        assert _should_exclude_key("feature_id") is True

    def test_normal_keys_not_excluded(self):
        assert _should_exclude_key("name") is False
        assert _should_exclude_key("temperature") is False
        assert _should_exclude_key("description") is False
        assert _should_exclude_key("wind_speed") is False

    def test_tricky_non_excluded(self):
        """Keys that contain 'id' but aren't ID fields."""
        assert _should_exclude_key("width") is False
        assert _should_exclude_key("grid") is False
        assert _should_exclude_key("video") is False


class TestHumanizeKey:
    """Tests for _humanize_key — converting property keys to readable labels."""

    def test_snake_case(self):
        assert _humanize_key("wind_speed") == "Wind Speed"

    def test_camel_case(self):
        assert _humanize_key("numberOfItems") == "Number Of Items"

    def test_single_word(self):
        assert _humanize_key("name") == "Name"

    def test_mixed_underscore_and_camel(self):
        assert _humanize_key("temp_celsius") == "Temp Celsius"

    def test_already_capitalised(self):
        assert _humanize_key("URL") == "Url"


class TestFormatValue:
    """Tests for _format_value — number formatting and unit suffix detection."""

    def test_integer_comma_formatted(self):
        assert _format_value("population", 1234567) == "1,234,567"

    def test_float_no_trailing_zeros(self):
        assert _format_value("score", 12.0) == "12"
        assert _format_value("score", 12.5) == "12.5"

    def test_celsius_suffix(self):
        assert _format_value("temp_celsius", 12) == "12 °C"

    def test_kmh_suffix(self):
        assert _format_value("speed_kmh", 45.2) == "45.2 km/h"

    def test_percent_suffix(self):
        assert _format_value("humidity_percent", 85) == "85 %"

    def test_string_passthrough(self):
        assert _format_value("name", "London") == "London"

    def test_none_returns_empty(self):
        assert _format_value("x", None) == ""

    def test_boolean_passthrough(self):
        assert _format_value("active", True) == "True"
        assert _format_value("active", False) == "False"

    def test_large_float_with_unit(self):
        assert _format_value("distance_km", 1234.5) == "1,234.5 km"


class TestOrderFields:
    """Tests for _order_fields — priority field ordering."""

    def test_priority_fields_first(self):
        result = _order_fields(["pop", "name", "type"])
        assert result == ["name", "type", "pop"]

    def test_no_priority_keys_preserves_order(self):
        result = _order_fields(["foo", "bar", "baz"])
        assert result == ["foo", "bar", "baz"]

    def test_empty_list(self):
        assert _order_fields([]) == []

    def test_all_priority(self):
        result = _order_fields(["status", "name", "description"])
        assert result == ["name", "description", "status"]

    def test_case_sensitive_match(self):
        """Priority matching is case-insensitive via lowercase map."""
        result = _order_fields(["Name", "pop"])
        assert result == ["Name", "pop"]


class TestPickTitle:
    """Tests for _pick_title — smart title template selection."""

    def test_name_only(self):
        title, used = _pick_title(["name", "temp"], {"name", "temp"})
        assert title == "{name}"
        assert used == ["name"]

    def test_name_and_type_compound(self):
        title, used = _pick_title(["name", "type", "temp"], {"name", "type", "temp"})
        assert title == "{name} — {type}"
        assert used == ["name", "type"]

    def test_name_and_category_compound(self):
        title, used = _pick_title(["name", "category"], {"name", "category"})
        assert title == "{name} — {category}"
        assert used == ["name", "category"]

    def test_title_key(self):
        title, used = _pick_title(["title", "desc"], {"title", "desc"})
        assert title == "{title}"
        assert used == ["title"]

    def test_label_key(self):
        title, used = _pick_title(["label", "value"], {"label", "value"})
        assert title == "{label}"
        assert used == ["label"]

    def test_no_known_keys_uses_first(self):
        title, used = _pick_title(["temp", "wind"], {"temp", "wind"})
        assert title == "{temp}"
        assert used == ["temp"]

    def test_empty_keys(self):
        title, used = _pick_title([], set())
        assert title == "{id}"
        assert used == ["id"]


class TestAutoPopupEnhanced:
    """Tests for the enhanced _auto_popup with filtering, ordering, and compound titles."""

    def test_excludes_internal_keys(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"_id": 1, "name": "London", "temp": 12},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup is not None
        assert popup.title == "{name}"
        # _id excluded, name in title, so fields = ["temp"]
        assert popup.fields == ["temp"]

    def test_compound_title_name_type(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"name": "Big Ben", "type": "Monument", "city": "London"},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup is not None
        assert popup.title == "{name} — {type}"
        assert "city" in popup.fields
        assert "name" not in popup.fields
        assert "type" not in popup.fields

    def test_all_keys_excluded_returns_none(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"_id": 1, "fid": 2, "objectid": 3},
                }
            ],
        }
        assert _auto_popup(fc) is None

    def test_fields_ordered_by_priority(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {"pop": 9000000, "name": "London", "description": "Capital"},
                }
            ],
        }
        popup = _auto_popup(fc)
        assert popup is not None
        assert popup.title == "{name}"
        # description should come before pop (priority ordering)
        assert popup.fields == ["description", "pop"]

    def test_no_features_returns_none(self):
        fc = {"type": "FeatureCollection", "features": []}
        assert _auto_popup(fc) is None

    def test_empty_properties_returns_none(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {},
                }
            ],
        }
        assert _auto_popup(fc) is None


class TestShowGeojsonAutoPopup:
    """Tests that show_geojson now auto-generates popups."""

    @pytest.mark.asyncio
    async def test_show_geojson_has_popup(self):
        geojson = json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-0.12, 51.5]},
                        "properties": {"name": "London", "temp": "12°C"},
                    }
                ],
            }
        )
        result = await show_geojson(geojson=geojson)
        layer = result.layers[0]
        assert layer.popup is not None
        assert layer.popup.title == "{name}"
        assert "temp" in layer.popup.fields

    @pytest.mark.asyncio
    async def test_show_geojson_no_properties_no_popup(self):
        geojson = json.dumps(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {},
            }
        )
        result = await show_geojson(geojson=geojson)
        assert result.layers[0].popup is None

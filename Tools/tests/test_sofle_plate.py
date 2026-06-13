# ABOUTME: Validates the generated Sofle mix production plates (all switch families) are
# ABOUTME: printable as one part: single watertight body, 60 caps, sane dimensions.

import os
import sys

import numpy as np
import pytest
import trimesh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from make_sofle_plate import (  # noqa: E402
    BAR_HEIGHT,
    BAR_WIDTH,
    FAMILIES,
    PLATE_ROWS,
    load_cap,
    plate_path,
    skirt_bottom_z,
)

# JLC3DP connected-parts rule: connection cross-sections must be >= 1.5mm, and
# 3.0mm keeps them unified rather than flagged as loose small parts.
JLC_MIN_CONNECTION = 1.5
JLC_UNIFIED_CONNECTION = 3.0


@pytest.fixture(scope="module", params=list(FAMILIES))
def family(request):
    return request.param


@pytest.fixture(scope="module")
def plate(family):
    path = plate_path(family)
    assert os.path.exists(path), (
        f"plate not generated yet — run Tools/make_sofle_plate.py first ({path})"
    )
    return trimesh.load(path, process=True)


def test_rows_total_56_plus_wides():
    assert sum(len(row) for row in PLATE_ROWS) == 56  # + 2x 1.25u + 2x 1.5u = 60


def test_plate_is_single_watertight_body(plate):
    assert plate.is_watertight, "plate must be watertight for print services"
    assert plate.is_winding_consistent
    components = plate.split(only_watertight=False)
    assert len(components) == 1, f"expected one fused body, got {len(components)}"


def test_plate_has_60_cap_walls(family, plate):
    # Slice low, where every cap (whatever its height) still shows a hollow
    # wall. Connector bars fuse the outer boundaries together, so cap count is
    # read from the interior holes: one cap-sized hole per cap. Slicing high
    # would miss the short caps, which have already closed into their dish.
    from shapely.geometry import Polygon

    cap = load_cap(family, "Normal")
    cap_area = np.prod((cap.bounds[1] - cap.bounds[0])[:2])
    slice_z = skirt_bottom_z(cap) + 0.6
    section = plate.section(plane_origin=[0, 0, slice_z], plane_normal=[0, 0, 1])
    assert section is not None
    planar, _ = section.to_2D()
    holes = sum(
        1
        for poly in planar.polygons_full
        for ring in poly.interiors
        if Polygon(ring).area > cap_area / 3
    )
    assert holes == 60, f"expected 60 cap walls in cross-section, found {holes}"


def test_plate_dimensions_fit_layout(plate):
    size = plate.bounds[1] - plate.bounds[0]
    assert size[0] < 165, f"plate too wide: {size[0]:.1f}mm"
    assert size[1] < 180, f"plate too deep: {size[1]:.1f}mm"
    assert size[2] < 12, f"plate too tall: {size[2]:.1f}mm"


def test_plate_file_size_uploadable(family):
    mb = os.path.getsize(plate_path(family)) / 1e6
    assert mb < 50, f"STL is {mb:.0f}MB — too large for print service upload"


def test_connection_bars_meet_jlc_minimum():
    # Both bar cross-section dimensions must clear JLC's unified-connection size
    # so the plate is accepted as one shell, not 60 loose small parts.
    assert min(BAR_WIDTH, BAR_HEIGHT) >= JLC_UNIFIED_CONNECTION


def test_horizontal_bridge_is_solid(family, plate):
    # The bar between the first two top-row caps must be a solid block at least
    # JLC's minimum across its cross-section. Probe a grid of points filling a
    # JLC_MIN_CONNECTION square at the bar centre and require all of them inside
    # the mesh, proving a continuous connection of that thickness exists.
    cap = load_cap(family, "Normal")
    pitch_x = (cap.bounds[1] - cap.bounds[0])[0] + 1.0
    bar_center_z = skirt_bottom_z(cap) + BAR_HEIGHT / 2
    half = JLC_MIN_CONNECTION / 2
    offs = np.linspace(-half, half, 5)
    pts = np.array([[pitch_x / 2, y, bar_center_z + z] for y in offs for z in offs])
    inside = plate.contains(pts)
    assert inside.all(), (
        f"{(~inside).sum()}/{len(pts)} probe points in the bridge are outside the "
        "mesh — connection thinner than JLC minimum"
    )


def test_wide_thumbs_are_wider_than_1u(family):
    # The native 1.25u/1.5u caps must be wider than 1u in exactly one axis.
    fam = FAMILIES[family]
    thumb = load_cap(family, "Thumb")
    base = (thumb.bounds[1] - thumb.bounds[0])[:2]
    for key, factor in (("wide_125", 0.25), ("wide_15", 0.5)):
        wide = load_cap(family, fam[key])
        size = (wide.bounds[1] - wide.bounds[0])[:2]
        assert abs(size[0] - base[0]) < 0.3, f"{fam[key]} width changed unexpectedly"
        assert size[1] > base[1] + factor * 3, f"{fam[key]} is not wider than 1u"

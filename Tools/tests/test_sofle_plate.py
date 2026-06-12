# ABOUTME: Validates the generated Sofle mix production plates (all switch families) are
# ABOUTME: printable as one part: single watertight body, 60 caps, sane dimensions.

import os
import sys

import numpy as np
import pytest
import trimesh

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from make_sofle_plate import (  # noqa: E402
    FAMILIES,
    PLATE_ROWS,
    load_cap,
    plate_path,
    skirt_bottom_z,
)


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
    # Slice just above the connector bars: every cap shows its hollow outer
    # wall there as a ring (a polygon with an interior). MX stem receptacles
    # are also rings but far smaller, so require wall-sized area too.
    fam = FAMILIES[family]
    names = ["Normal", "Tilted", "Thumb", fam["wide_125"], fam["wide_15"]]
    bar_top = max(skirt_bottom_z(load_cap(family, n)) for n in names) + 1.0
    section = plate.section(plane_origin=[0, 0, bar_top + 0.4], plane_normal=[0, 0, 1])
    assert section is not None
    planar, _ = section.to_2D()
    cap = load_cap(family, "Normal")
    cap_area = np.prod((cap.bounds[1] - cap.bounds[0])[:2])
    walls = [p for p in planar.polygons_full if p.interiors and p.area > cap_area / 10]
    assert len(walls) == 60, f"expected 60 cap walls in cross-section, found {len(walls)}"


def test_plate_dimensions_fit_layout(plate):
    size = plate.bounds[1] - plate.bounds[0]
    assert size[0] < 165, f"plate too wide: {size[0]:.1f}mm"
    assert size[1] < 180, f"plate too deep: {size[1]:.1f}mm"
    assert size[2] < 12, f"plate too tall: {size[2]:.1f}mm"


def test_plate_file_size_uploadable(family):
    mb = os.path.getsize(plate_path(family)) / 1e6
    assert mb < 50, f"STL is {mb:.0f}MB — too large for print service upload"


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

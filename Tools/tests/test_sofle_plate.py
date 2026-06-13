# ABOUTME: Validates the committed Sofle order files (the <=9-cap split STLs) satisfy JLC3DP's
# ABOUTME: max-10-parts-per-file rule and together hold the full 60-cap set per family.

import glob
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
)

# JLC3DP accepts at most 10 small parts (caps) per file; upstream uses 9.
JLC_MAX_PARTS = 10
CAP_MIN_FOOTPRINT = 10.0  # mm; caps are ~18mm, connector bars are <=4mm


@pytest.fixture(scope="module", params=list(FAMILIES))
def family(request):
    return request.param


def split_files(family):
    folder = os.path.dirname(plate_path(family))
    return sorted(glob.glob(os.path.join(folder, "*_9pc_*.stl")))


def cap_bodies(mesh):
    return [b for b in mesh.split(only_watertight=False)
            if (b.bounds[1] - b.bounds[0])[0] > CAP_MIN_FOOTPRINT]


def test_rows_total_56_plus_wides():
    assert sum(len(row) for row in PLATE_ROWS) == 56  # + 2x 1.25u + 2x 1.5u = 60


def test_split_files_exist(family):
    assert split_files(family), f"no _9pc_ order files for {family} — run split_for_jlc.py"


def test_each_file_within_jlc_part_limit(family):
    # The rule that actually gates JLC approval: <=10 caps per file.
    for f in split_files(family):
        caps = cap_bodies(trimesh.load(f, process=True))
        assert len(caps) <= JLC_MAX_PARTS, (
            f"{os.path.basename(f)} has {len(caps)} caps, over JLC's {JLC_MAX_PARTS} limit"
        )


def test_caps_are_watertight_and_complete(family):
    # Every cap watertight, and the files together hold the full 60-cap set.
    total = 0
    for f in split_files(family):
        caps = cap_bodies(trimesh.load(f, process=True))
        assert all(c.is_watertight for c in caps), f"non-watertight cap in {os.path.basename(f)}"
        total += len(caps)
    assert total == 60, f"{family}: split files hold {total} caps, expected 60"


def test_files_are_uploadable(family):
    for f in split_files(family):
        mb = os.path.getsize(f) / 1e6
        assert mb < 50, f"{os.path.basename(f)} is {mb:.0f}MB — too large to upload"


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

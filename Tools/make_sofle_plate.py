# ABOUTME: Generates production STLs with the full 58-key Sofle GammaCaps mix for every
# ABOUTME: switch family, caps fused by connector bars for one-part print-service orders.

import argparse
import os

import numpy as np
import trimesh
import fast_simplification
import manifold3d as m3d

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Switch families mirror the upstream STL folders. key_pitch is the keyboard
# unit spacing. The Sofle rotates its widest thumb key, so choc families use
# the rotated-stem (90) wide thumbs; MX stems are symmetric and need no 90.
FAMILIES = {
    "MX": {
        "prefix": "MX",
        "wide_125": "Thumb_1_25u",
        "wide_15": "Thumb_1_5u",
    },
    "Choc": {
        "prefix": "Choc",
        "wide_125": "Thumb_90_1_25u",
        "wide_15": "Thumb_90_1_5u",
    },
    "Choc (MX Spacing)": {
        "prefix": "Choc(MX)",
        "wide_125": "Thumb_90_1_25u",
        "wide_15": "Thumb_90_1_5u",
    },
}

# Caps sit 1mm apart, bridged by bars that weld into the cap skirts. JLC3DP's
# connected-parts rule requires every connection cross-section to be at least
# 1.5mm (3.0mm to guarantee the parts stay unified and aren't flagged as loose
# small parts), so the bars are a 3.0mm-wide x 3.0mm-tall solid that bridges
# the gap and overlaps each cap wall by ~1.5mm.
# https://jlc3dp.com/help/article/213-Connected-Parts-Printing-Guide
CAP_GAP = 1.0
BAR_WIDTH = 3.0
BAR_LENGTH = 4.0
BAR_HEIGHT = 3.0

# Sofle v2 mix, same sculpt logic as SOFLE_PRINT_MIX.md in KLP-Lame-Keycaps:
# tilted variants on the two outermost rows, saddle home row, flat upper row.
# GammaCaps names map as: Tilted_Saddle = number row, Normal = upper row,
# Normal_Saddle (+Homing) = home row, Tilted = bottom row.
PLATE_ROWS = [
    ["Tilted_Saddle"] * 8,
    ["Tilted_Saddle"] * 4 + ["Normal"] * 4,
    ["Normal"] * 8,
    ["Normal_Saddle"] * 8,
    ["Normal_Saddle"] * 2 + ["Normal_Saddle_Homing"] * 2 + ["Tilted"] * 4,
    ["Tilted"] * 8,
    ["Thumb"] * 8,
]
VARIANTS = ["Tilted_Saddle", "Normal", "Normal_Saddle", "Normal_Saddle_Homing", "Tilted", "Thumb"]

DECIMATE_TARGET = 12000
DECIMATE_MAX_ERROR = 0.1  # mm; matches SLA print service dimensional tolerance

# Upstream STLs are exported Y-up; rotate to Z-up for layout.
Y_UP_TO_Z_UP = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])


def load_cap(family, name):
    """Load a cap STL as Z-up, centered on xy origin, resting near z=0."""
    path = os.path.join(
        REPO_ROOT, "STL", family, f"gammacap - {FAMILIES[family]['prefix']}_{name}.STL"
    )
    cap = trimesh.load(path, process=True)
    cap.apply_transform(Y_UP_TO_Z_UP)
    center = (cap.bounds[0][:2] + cap.bounds[1][:2]) / 2
    cap.vertices[:, :2] -= center
    if not cap.is_watertight:
        raise ValueError(f"{path} is not watertight")
    return cap


def plate_path(family):
    return os.path.join(
        REPO_ROOT, "Production", family, f"gammacap_{FAMILIES[family]['prefix']}_Sofle_Mix.stl"
    )


def skirt_bottom_z(cap):
    """Lowest z of the cap's outer wall (a protruding stem doesn't count)."""
    size = cap.bounds[1] - cap.bounds[0]
    perim = (np.abs(cap.vertices[:, 0]) > size[0] / 2 - 1.0) | (
        np.abs(cap.vertices[:, 1]) > size[1] / 2 - 1.0
    )
    return cap.vertices[perim][:, 2].min()


def to_manifold(mesh):
    m = m3d.Mesh(mesh.vertices.astype(np.float32), mesh.faces.astype(np.uint32))
    m.merge()
    manifold = m3d.Manifold(m)
    if manifold.status() != m3d.Error.NoError:
        raise ValueError(f"mesh is not manifold: {manifold.status()}")
    return manifold


def to_trimesh(manifold):
    out = manifold.to_mesh()
    # manifold3d's output is topologically closed by vertex index — keep it
    # unprocessed if trimesh agrees (position-welding can fuse distinct
    # vertices that merely touch, breaking topology that was fine).
    raw = trimesh.Trimesh(
        out.vert_properties[:, :3].astype(np.float64), out.tri_verts, process=False
    )
    if raw.is_watertight:
        return raw
    # Otherwise weld float32 near-duplicates, escalating the grid only as
    # needed, and drop the degenerate faces the welding collapses.
    for digits in (4, 3):
        mesh = raw.copy()
        mesh.merge_vertices(digits_vertex=digits)
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
        mesh.process()
        if mesh.is_watertight:
            break
    return mesh


def decimate(mesh, target):
    """Reduce face count, verifying the surface stays within print tolerance."""
    points, faces = fast_simplification.simplify(
        mesh.vertices.astype(np.float32), mesh.faces.astype(np.uint32), target_count=target
    )
    slim = trimesh.Trimesh(points, faces)
    slim.process()
    if not slim.is_watertight:
        raise ValueError("decimated mesh lost watertightness")
    samples, _ = trimesh.sample.sample_surface(mesh, 5000, seed=42)
    _, dist, _ = trimesh.proximity.closest_point(slim, samples)
    if dist.max() > DECIMATE_MAX_ERROR:
        raise ValueError(f"decimation error {dist.max():.4f}mm exceeds {DECIMATE_MAX_ERROR}mm")
    return slim


def bar(x, y, z_range, along_x):
    extents = [BAR_LENGTH, BAR_WIDTH, z_range[1] - z_range[0]]
    if not along_x:
        extents = [BAR_WIDTH, BAR_LENGTH, extents[2]]
    box = trimesh.creation.box(
        extents=extents,
        transform=trimesh.transformations.translation_matrix([x, y, (z_range[0] + z_range[1]) / 2]),
    )
    return to_manifold(box)


def build_plate(family):
    fam = FAMILIES[family]
    wide_thumbs = (fam["wide_125"],) * 2 + (fam["wide_15"],) * 2
    print(f"[{family}] preparing cap meshes...")
    caps = {}
    skirts = {}
    for name in VARIANTS + list(set(wide_thumbs)):
        raw = load_cap(family, name)
        skirts[name] = skirt_bottom_z(raw)
        caps[name] = decimate(raw, DECIMATE_TARGET)

    # Bars span BAR_HEIGHT upward from the lowest skirt, so every cap's wall is
    # overlapped and the connection cross-section is a solid BAR_WIDTH x
    # BAR_HEIGHT. Verify the bar welds into the highest-skirt caps and stays
    # below the shortest cap top (so it never breaks through a dished surface).
    min_skirt, max_skirt = min(skirts.values()), max(skirts.values())
    shortest_top = min(c.bounds[1][2] for c in caps.values())
    bar_z = (min_skirt, min_skirt + BAR_HEIGHT)
    assert bar_z[1] > max_skirt + 1.0, "bar too short to weld into the tallest skirt"
    assert bar_z[1] < shortest_top - 0.3, "bar would break through the shortest cap top"

    size = caps["Normal"].bounds[1] - caps["Normal"].bounds[0]
    cap_w, cap_d = size[0], size[1]
    pitch_x, pitch_y = cap_w + CAP_GAP, cap_d + CAP_GAP

    print(f"[{family}] placing caps and connector bars...")
    parts = []
    used = {name: 0 for name in VARIANTS + list(set(wide_thumbs))}
    for r, row in enumerate(PLATE_ROWS):
        y = -r * pitch_y
        for c, name in enumerate(row):
            parts.append(to_manifold(caps[name]).translate([c * pitch_x, y, 0]))
            used[name] += 1
            if c > 0:
                parts.append(bar(c * pitch_x - pitch_x / 2, y, bar_z, along_x=True))
            if r > 0:
                parts.append(bar(c * pitch_x, y + pitch_y / 2, bar_z, along_x=False))

    # Wide-thumb row: caps differ in footprint, so align their top edges one
    # gap below the thumb row and advance the x cursor per cap width.
    top_edge_y = -(len(PLATE_ROWS) - 1) * pitch_y - cap_d / 2 - CAP_GAP
    gap_y = top_edge_y + CAP_GAP / 2
    cursor = 0.0
    prev_edge = None
    for name in wide_thumbs:
        w, d = (caps[name].bounds[1] - caps[name].bounds[0])[:2]
        cx = cursor + w / 2
        parts.append(to_manifold(caps[name]).translate([cx, top_edge_y - d / 2, 0]))
        used[name] += 1
        col_x = min(7, max(0, round(cx / pitch_x))) * pitch_x
        col_x = min(max(col_x, cx - w / 2 + BAR_WIDTH), cx + w / 2 - BAR_WIDTH)
        parts.append(bar(col_x, gap_y, bar_z, along_x=False))
        if prev_edge is not None:
            parts.append(bar(prev_edge + CAP_GAP / 2, top_edge_y - 7.0, bar_z, along_x=True))
        prev_edge = cursor + w
        cursor += w + CAP_GAP

    expected = {"Tilted_Saddle": 12, "Normal": 12, "Normal_Saddle": 10,
                "Normal_Saddle_Homing": 2, "Tilted": 12, "Thumb": 8,
                fam["wide_125"]: 2, fam["wide_15"]: 2}
    if used != expected:
        raise ValueError(f"layout does not match mix: {used} != {expected}")

    print(f"[{family}] fusing {len(parts)} parts...")
    plate = m3d.Manifold.batch_boolean(parts, m3d.OpType.Add)
    if plate.status() != m3d.Error.NoError:
        raise ValueError(f"union failed: {plate.status()}")
    if len(plate.decompose()) != 1:
        raise ValueError("plate has disconnected bodies")

    result = to_trimesh(plate)
    if not result.is_watertight:
        raise ValueError("plate is not watertight")

    path = plate_path(family)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    result.export(path)
    size = result.bounds[1] - result.bounds[0]
    print(f"[{family}] wrote {os.path.basename(path)}: {os.path.getsize(path) / 1e6:.1f} MB, "
          f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm, 60 caps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=list(FAMILIES), help="build a single family")
    args = parser.parse_args()
    for family in ([args.family] if args.family else FAMILIES):
        build_plate(family)


if __name__ == "__main__":
    main()

# ABOUTME: Splits a multi-body keycap STL into files of <=9 caps, each a SINGLE connected
# ABOUTME: cluster (overlapping connector bars), as JLC3DP requires one merge-able shell per file.

# JLC3DP accepts at most ~10 small parts per file (upstream uses 9) AND each file
# must form one part: it auto-merges overlapping bodies, but a file containing two
# clusters that don't touch is rejected ("multiple shells which cannot be merged").
# So every group here is forced into one connected cluster — adjacency bars plus, if
# a group still has separate clusters, bridge bars between the nearest caps.
# https://jlc3dp.com/help/article/213-Connected-Parts-Printing-Guide

import argparse
import os

import numpy as np
import trimesh

GROUP = 9          # caps per file (<= 10; upstream uses 9)
BAR_WIDTH = 3.0
BAR_HEIGHT = 2.0   # sturdier than upstream's 0.9mm so groups survive shipping
BAR_OVERLAP = 2.0  # how far a bar reaches into each cap it joins
ADJACENT = 1.4     # caps within this * grid pitch get an adjacency bar


def skirt_bottom(cap):
    c = (cap.bounds[0] + cap.bounds[1]) / 2
    sz = cap.bounds[1] - cap.bounds[0]
    v = cap.vertices
    perim = (np.abs(v[:, 0] - c[0]) > sz[0] / 2 - 1.0) | (np.abs(v[:, 1] - c[1]) > sz[1] / 2 - 1.0)
    return v[perim][:, 2].min()


def bar_between(a, b):
    """A box that spans the gap between two caps and overlaps BAR_OVERLAP into
    each, oriented along whichever axis separates them — so it works for both
    snug grid neighbours and the larger thumb-row-to-wide-row bridge."""
    ca, cb = a.centroid, b.centroid
    sa, sb = a.bounds[1] - a.bounds[0], b.bounds[1] - b.bounds[0]
    axis = 0 if abs(cb[0] - ca[0]) >= abs(cb[1] - ca[1]) else 1
    sign = 1.0 if cb[axis] >= ca[axis] else -1.0
    a_edge = ca[axis] + sign * sa[axis] / 2
    b_edge = cb[axis] - sign * sb[axis] / 2
    length = abs(b_edge - a_edge) + 2 * BAR_OVERLAP
    center = np.array([(ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2, 0.0])
    center[axis] = (a_edge + b_edge) / 2
    z0 = min(skirt_bottom(a), skirt_bottom(b))
    center[2] = z0 + BAR_HEIGHT / 2
    extents = [BAR_WIDTH, BAR_WIDTH, BAR_HEIGHT]
    extents[axis] = length
    return trimesh.creation.box(extents=extents,
                                transform=trimesh.transformations.translation_matrix(center))


def _root(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def connect_group(members, cents, pitch):
    """Return the bars that make `members` (indices into cents) one cluster:
    adjacency bars, then bridge bars between nearest caps of separate clusters."""
    m = len(members)
    parent = list(range(m))
    bars, edges = [], []
    for i in range(m):
        for j in range(i + 1, m):
            if np.linalg.norm(cents[members[i]] - cents[members[j]]) < ADJACENT * pitch:
                edges.append((i, j))
    for i, j in edges:
        parent[_root(parent, i)] = _root(parent, j)
        bars.append((members[i], members[j]))
    # bridge remaining clusters by repeatedly joining the closest cross-cluster pair
    while len({_root(parent, i) for i in range(m)}) > 1:
        best = None
        for i in range(m):
            for j in range(i + 1, m):
                if _root(parent, i) != _root(parent, j):
                    dist = np.linalg.norm(cents[members[i]] - cents[members[j]])
                    if best is None or dist < best[0]:
                        best = (dist, i, j)
        _, i, j = best
        parent[_root(parent, i)] = _root(parent, j)
        bars.append((members[i], members[j]))
    return bars


def split_file(path, group=GROUP, out_dir=None):
    mesh = trimesh.load(path, process=True)
    caps = mesh.split(only_watertight=False)
    cents = np.array([c.centroid for c in caps])
    d = np.linalg.norm(cents[:, None] - cents[None, :], axis=2)
    np.fill_diagonal(d, np.inf)
    pitch = float(np.median(d.min(axis=1)))

    # Group by keyboard row, not by a flat count: each row is a spatially
    # contiguous strip that connects into one cluster with a simple chain of
    # bars. (Flat chunking can strand a few caps in a far corner of the file,
    # which JLC rejects as "multiple shells that cannot be merged".)
    groups = []
    for i in sorted(range(len(caps)), key=lambda i: -cents[i][1]):
        if groups and abs(cents[groups[-1][-1]][1] - cents[i][1]) <= pitch * 0.6 \
                and len(groups[-1]) < group:
            groups[-1].append(i)
        else:
            groups.append([i])
    for g in groups:
        g.sort(key=lambda i: cents[i][0])

    n_files = len(groups)
    base = os.path.splitext(os.path.basename(path))[0].replace("_Nylon", "")
    out_dir = out_dir or os.path.dirname(path)
    os.makedirs(out_dir, exist_ok=True)

    written = []
    for f, members in enumerate(groups):
        bar_pairs = connect_group(members, cents, pitch)
        bodies = [caps[i] for i in members] + [bar_between(caps[i], caps[j]) for i, j in bar_pairs]
        out_mesh = trimesh.util.concatenate(bodies)
        out_mesh.apply_translation(-out_mesh.bounds[0])
        # verify one connected cluster (bbox-overlap graph) before writing
        assert _one_cluster(bodies), f"{base} file {f + 1}: caps not all connected"
        out = os.path.join(out_dir, f"{base}_{group}pc_{f + 1}of{n_files}.stl")
        out_mesh.export(out)
        written.append((out, len(members), len(bar_pairs)))
    return written


def _one_cluster(bodies):
    n = len(bodies)
    parent = list(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            a, b = bodies[i].bounds, bodies[j].bounds
            if (a[0][0] <= b[1][0] and a[1][0] >= b[0][0] and
                    a[0][1] <= b[1][1] and a[1][1] >= b[0][1] and
                    a[0][2] <= b[1][2] and a[1][2] >= b[0][2]):
                parent[_root(parent, i)] = _root(parent, j)
    return len({_root(parent, i) for i in range(n)}) == 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="multi-body STL(s) to split")
    parser.add_argument("--group", type=int, default=GROUP, help="caps per file (<=10)")
    parser.add_argument("--out", help="output directory (default: next to source)")
    args = parser.parse_args()
    for path in args.files:
        for out, caps, bars in split_file(path, args.group, args.out):
            print(f"wrote {os.path.basename(out)} ({caps} caps, {bars} bars)")


if __name__ == "__main__":
    main()

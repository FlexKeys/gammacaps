# Sofle Print Mix — GammaCaps

Print mix for a Sofle v2 / Sofle Choc (58 keys: 4×6 matrix per half + 5 thumbs
per half), using the same row-sculpt logic as the KLP Lamé Sofle mix: tilted
variants on the two outermost rows, saddle home row, flat upper row.

## Mix per keyboard (58 caps)

| Qty | GammaCaps variant      | Goes on                                       |
| --: | :--------------------- | :--------------------------------------------- |
|  12 | Tilted Saddle           | Number row (tilt faces fingers)               |
|  12 | Normal                  | Upper row (above home)                        |
|  10 | Normal Saddle           | Home row (minus the two homing keys)          |
|   2 | Normal Saddle Homing    | F and J home positions                        |
|  12 | Tilted                  | Bottom row (rotate cap 180° so tilt faces up) |
|   8 | Thumb                   | Outer 1u thumb keys (4 per half)              |
|   2 | Thumb 1.25u or 1.5u     | Inner (widest) thumb key, one per half        |

The Sofle rotates its widest thumb key, so the choc families use the
rotated-stem `Thumb_90` wide variants; MX stems are symmetric and use the
plain wide thumbs.

## Order files: `*_9pc_*.stl` (JLC3DP)

JLC3DP accepts at most **10 small parts per file** for both resin (SLA) and
nylon (MJF/SLS) — a single 60-cap file is rejected on the part count whether
it's one fused shell or loose bodies (we tried both; both failed). JLC also
rejects any file whose parts don't all connect into one merge-able shell. The
proven fix is to ship the set as several files of **≤9 caps each, every file a
single connected strip** held together by light connector bars.

So each family's full 60-cap mix is split by keyboard row into **eight
`*_9pc_*.stl` files** under `Production/<family>/` (seven rows of 8 caps + one
of 4). Each file is one contiguous row, so it always merges into a single
shell. Upload all eight for your family, order quantity 1 of each. The **same
eight files work for both resin and nylon** — the process/material is just a
setting in JLC's order form:

- **Resin (SLA):** the bars hold each group together through the resin process;
  snip them with flush cutters after printing.
- **Nylon (MJF/SLS):** the powder bed nests the groups, no supports; snip the
  same small bars after printing.

Connection thickness does **not** matter at ≤10 caps — upstream's own bars are
only ~0.9mm and pass. (Earlier single-plate attempts, even a clean watertight
shell with 3mm bars, were rejected purely on the >10 part count.)
https://jlc3dp.com/help/article/213-Connected-Parts-Printing-Guide

| Family            | Files (`Production/<family>/`)            | For                    |
| :---------------- | :---------------------------------------- | :--------------------- |
| MX                | `gammacap_MX_Sofle_Mix_9pc_1of8…8of8`     | MX switches            |
| Choc              | `gammacap_Choc_Sofle_Mix_9pc_1of8…8of8`   | Choc switches          |
| Choc (MX Spacing) | `gammacap_Choc(MX)_Sofle_Mix_9pc_1of8…`   | Choc on MX spacing     |

Each family's eight files together hold the full mix plus both wide-thumb
options (2 × 1.25u + 2 × 1.5u), so the unused thumb pair is spares. Row map of
the full set: Tilted Saddle ×8 | Tilted Saddle ×4 + Normal ×4 | Normal ×8 |
Normal Saddle ×8 | Normal Saddle ×2 + Homing ×2 + Tilted ×4 | Tilted ×8 |
Thumb ×8 | Thumb 1.25u ×2 + Thumb 1.5u ×2.

Generation (`Tools/make_sofle_plate.py` then `Tools/split_for_jlc.py`,
validated by `Tools/tests/test_sofle_plate.py`): caps are decimated with a
verified surface error under 0.1mm. Upstream meshes are all watertight and the
wide thumbs are native — no geometry surgery needed. Source STLs are exported
Y-up; the generator rotates them to Z-up.

Material guidance (community-tested — see KLP-Lame-Keycaps/SOFLE_PRINT_MIX.md
for sources): SLA in JLC Black Resin is the cheap reliable order; MJF PA12-HP
nylon (black, never PA12S-HP) feels best. Skip sanding finishes — they loosen
stem fit.

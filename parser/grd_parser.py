"""
GRD Parser — matches MATLAB parseGrdAll logic exactly.

Reads multi-block GRASP .grd files.
Each block:
  Line 1: x_start  y_start  x_end  y_end   (4 floats)
  Line 2: nx  ny  [extra ints ignored]
  Next lines: nx*ny*4 floats (Eco_re, Eco_im, Ecx_re, Ecx_im) per sample
              stored column-major: outer index = x (theta_x), inner = y (theta_y)

Returns list of dicts with keys:
  theta_x   (nx,) array   — x-axis direction cosine / angle grid
  theta_y   (ny,) array   — y-axis
  eco_lin   (ny, nx) array — co-pol linear amplitude (peak-normalised, 0..1)
  ecx_lin   (ny, nx) array — cross-pol linear amplitude (peak-normalised)
  peak      float          — raw peak before normalisation

NOTE: linear grids are stored so the cut engine can interpolate in linear
space and convert to dB after — this avoids the spiky-null artefact that
occurs when interpolating directly in dB space.
"""

import numpy as np


def parse_grd_all(filepath):
    with open(filepath, 'r') as fh:
        lines = fh.read().splitlines()

    n_lines = len(lines)

    # ── locate block starts ────────────────────────────────────────────────
    block_starts = []
    i = 0
    while i <= n_lines - 2:
        bv = _parse_floats(lines[i])
        if len(bv) == 4:
            gv = _parse_ints(lines[i + 1])
            if len(gv) >= 2 and gv[0] > 0 and gv[1] > 0:
                block_starts.append(i)
                nx, ny = gv[0], gv[1]
                skip = 2 + int(np.ceil(nx * ny * 4 / 4))
                i += skip
                continue
        i += 1

    if not block_starts:
        raise ValueError('No valid data blocks found in file.')

    n_blocks = len(block_starts)
    all_data = []

    for b in range(n_blocks):
        i = block_starts[b]
        bv = _parse_floats(lines[i]);  i += 1
        x_start, y_start, x_end, y_end = bv[0], bv[1], bv[2], bv[3]

        gv = _parse_ints(lines[i]);  i += 1
        nx, ny = gv[0], gv[1]

        total = nx * ny * 4
        buf = []
        while len(buf) < total and i < n_lines:
            buf.extend(_parse_floats(lines[i]))
            i += 1
        buf = np.array(buf[:total], dtype=np.float64)

        # arr shape: (nx*ny, 4)
        arr = buf.reshape(nx * ny, 4)

        # eco2/ecx2: amplitude grids shaped (ny, nx) — rows=y, cols=x
        eco2 = np.abs(arr[:, 0] + 1j * arr[:, 1]).reshape(nx, ny).T
        ecx2 = np.abs(arr[:, 2] + 1j * arr[:, 3]).reshape(nx, ny).T

        pk = eco2.max()
        if pk == 0:
            pk = 1.0
        fl = pk * 1e-10

        theta_x = np.linspace(x_start, x_end, nx)
        theta_y = np.linspace(y_start, y_end, ny)

        all_data.append(dict(
            theta_x=theta_x,
            theta_y=theta_y,
            eco_lin=eco2 / pk,          # linear 0..1, interpolate in this space
            ecx_lin=ecx2 / pk,
            floor=fl / pk,              # normalised floor for dB clamp
            peak=pk,
        ))

    return all_data, n_blocks


# ── helpers ────────────────────────────────────────────────────────────────

def _parse_floats(line):
    try:
        return [float(x) for x in line.split()]
    except ValueError:
        return []


def _parse_ints(line):
    vals = []
    for tok in line.split():
        try:
            vals.append(int(tok))
        except ValueError:
            pass
    return vals

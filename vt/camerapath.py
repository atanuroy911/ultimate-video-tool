"""A camera path a cinematographer would have shot: still, or a steady pan, never a jitter that chases the face.

When a wide video is cropped vertical the crop must follow the speaker, but following the detected face frame by frame
gives a nervous picture. Grundmann, Kwatra & Essa, "Auto-Directed Video Stabilization with Robust L1 Optimal Camera Paths"
(CVPR 2011) solve this as a linear programme: minimise the L1 norm of the path's first, second and third derivatives, so the
optimum is made of constant, linear and parabolic pieces (a locked shot, a pan, an ease), subject to the path staying within a
margin of where the subject is (the face stays inside the crop). The L1 norm, unlike L2, lets the path be exactly still for long
stretches and change in a few places.

`optimal_path(centres, margin)` returns the smoothed path at the same sample rate; `knots(path)` reduces it to the few times
where the motion changes, which is what the renderer interpolates between.
"""
from __future__ import annotations

import numpy as np

DERIVATIVE_WEIGHTS = (10.0, 1.0, 100.0)     # first, second, third derivative, as in the paper (w1=10, w2=1, w3=100)


def _difference_matrix(n: int, order: int) -> np.ndarray:
    d = np.eye(n)
    for _ in range(order):
        d = d[1:] - d[:-1]
    return d


def optimal_path(centres: np.ndarray, margin: float, weights: tuple[float, float, float] = DERIVATIVE_WEIGHTS) -> np.ndarray:
    """The smoothest path p with |p_t − c_t| ≤ margin for every sample (an L1 trend filter with box constraints).
    `centres` are the subject's positions as fractions (0..1), NaN where nothing was seen (unconstrained there)."""
    from scipy.optimize import linprog

    c = np.asarray(centres, dtype=float)
    n = len(c)
    if n == 0:
        return c
    if n <= 3:
        return np.full(n, float(np.nanmedian(c)) if np.isfinite(c).any() else 0.5)
    # variables: p (n), then one slack per row of each derivative (e_k ≥ |D_k p|)
    blocks = [(_difference_matrix(n, k + 1), w) for k, w in enumerate(weights) if w > 0]
    slack_sizes = [d.shape[0] for d, _ in blocks]
    total = n + sum(slack_sizes)
    cost = np.zeros(total)
    offset = n
    for (d, w), size in zip(blocks, slack_sizes):
        cost[offset:offset + size] = w
        offset += size
    # |D p| ≤ e  ⇔  D p − e ≤ 0 and −D p − e ≤ 0
    rows, rhs = [], []
    offset = n
    for (d, w), size in zip(blocks, slack_sizes):
        slack = np.zeros((size, total))
        slack[:, offset:offset + size] = -np.eye(size)
        lhs = np.zeros((size, total))
        lhs[:, :n] = d
        rows.append(lhs + slack)
        rows.append(-lhs + slack)
        rhs.extend([0.0] * (2 * size))
        offset += size
    a_ub = np.vstack(rows)
    b_ub = np.asarray(rhs)
    bounds = []
    for value in c:
        if np.isfinite(value):
            bounds.append((max(0.0, value - margin), min(1.0, value + margin)))
        else:
            bounds.append((0.0, 1.0))
    bounds += [(0, None)] * (total - n)
    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not result.success:
        return np.where(np.isfinite(c), c, np.nanmedian(c) if np.isfinite(c).any() else 0.5)
    return result.x[:n]


def knots(path: np.ndarray, tolerance: float = 0.01) -> list[int]:
    """Sample indices where the path's slope changes (the start of every still, pan or ease), always including the ends."""
    p = np.asarray(path, dtype=float)
    n = len(p)
    if n <= 2:
        return list(range(n))
    out = [0]
    slope = p[1] - p[0]
    for i in range(1, n - 1):
        next_slope = p[i + 1] - p[i]
        if abs(next_slope - slope) > tolerance:
            out.append(i)
            slope = next_slope
    out.append(n - 1)
    return out

"""Off-design laws and the load sweep (quasi-off-design).

Method (stated openly in the README): every load point is re-solved in
TESPy *design* mode with load-dependent setpoints. This is a
quasi-off-design calculation, not TESPy's native ``mode='offdesign'``:
native offdesign would impose TESPy's own default characteristics
(turbine cone law, heat-exchanger kA from the design point) and hide the
load laws; the re-solve keeps every law explicit and auditable below.

Load laws (all parameters are stated here, none is fitted to the heat
rate, which is an *output* of the calculation):

- Sliding pressure (Stodola approximation): all turbine-stage pressures
  scale with the load fraction ``f``; the condenser pressure stays fixed
  at 7 kPa and the main/reheat steam temperatures stay at 566 degC.
- Turbine isentropic efficiency: quadratic drop,
  ``eta_s(f) = eta_s,design - a * (1 - f)**2``. The ``a`` values are chosen
  from the cylinder-efficiency drops measured in Zhang et al. (2025)
  between 630 MW and 105 MW (HP 84.12% -> 69.15%, IP 87.86% -> 86.25%,
  LP 85.86% -> 79.58%): the HP cylinder's large, non-monotonic drop is
  caused by regulating-valve sequencing, which a smooth law cannot
  reproduce, so the HP law uses a moderate ``a`` and the README says so.
- Boiler efficiency and auxiliary (plant) power rate: piecewise-linear
  interpolation through the values *measured* in Zhang et al. (2025).
  The 630 MW boiler efficiency is not stated in the paper (only that the
  maximum, 93.58%, occurs at 475 MW and that it "changes little" above
  40% load), so the design point is taken as 93.3% and labelled as an
  assumption in the README.
"""

from __future__ import annotations

import numpy as np

#: Quadratic efficiency-drop coefficients per turbine stage group.
ETA_S_DROP = {"hp": 0.08, "ip": 0.03, "lp1": 0.07, "lp2": 0.07}

#: Design-point isentropic efficiencies (imported here to avoid a cycle).
ETA_S_DESIGN = {"hp": 0.89, "ip": 0.90, "lp1": 0.89, "lp2": 0.86}

#: Boiler efficiency anchors: (load fraction, efficiency), measured in
#: Zhang et al. (2025) except the 1.0 point (assumption, see module doc).
BOILER_EFFICIENCY_ANCHORS = (
    (1.000, 0.933),
    (0.754, 0.9358),
    (0.381, 0.9279),
    (0.167, 0.8961),
)

#: Auxiliary power rate anchors: (load fraction, rate), all measured.
AUX_RATE_ANCHORS = (
    (1.000, 0.0526),
    (0.754, 0.0463),
    (0.476, 0.0508),
    (0.167, 0.1222),
)


def turbine_eta_s(stage: str, load_fraction: float) -> float:
    """Isentropic efficiency of a turbine stage group at ``load_fraction``."""
    f = load_fraction
    return ETA_S_DESIGN[stage] - ETA_S_DROP[stage] * (1.0 - f) ** 2


def _interp_clamped(x: float, anchors) -> float:
    pts = sorted(anchors)  # np.interp needs ascending x
    xs = np.array([a[0] for a in pts])
    ys = np.array([a[1] for a in pts])
    return float(np.interp(x, xs, ys))


def boiler_efficiency(load_fraction: float) -> float:
    """Boiler efficiency at ``load_fraction`` (piecewise-linear anchors)."""
    return _interp_clamped(load_fraction, BOILER_EFFICIENCY_ANCHORS)


def aux_rate(load_fraction: float) -> float:
    """Plant auxiliary power rate at ``load_fraction`` (measured anchors)."""
    return _interp_clamped(load_fraction, AUX_RATE_ANCHORS)


def sweep(
    load_fractions=(1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3),
    design=None,
    tol_frac: float = 0.003,
    max_iter: int = 4,
):
    """Sweep the load range and return one result per load fraction.

    Each point is solved so that its *net* power equals
    ``load_fraction * 630 MW`` (secant on the main-steam flow, starting
    from ``load_fraction * design`` flow). Points are solved from high to
    low load and each solution seeds the next point's starting values.
    """
    from .cycle import RATED_NET_POWER_KW, solve_point

    if design is None:
        from .cycle import calibrate_design

        design = calibrate_design()
    m_design = design.main_steam_flow_kg_per_s
    results = []
    start = None
    for f in sorted(load_fractions, reverse=True):
        target_kw = f * RATED_NET_POWER_KW
        if abs(f - 1.0) < 1e-9:
            results.append(design)
            start = design.states
            continue
        m0 = f * m_design
        r0 = solve_point(f, m0, start=start)
        m1 = m0 * (target_kw / r0.net_power_kw)
        r1 = solve_point(f, m1, start=r0.states)
        for _ in range(max_iter):
            err = r1.net_power_kw - target_kw
            if abs(err) <= tol_frac * target_kw:
                break
            slope = (r1.net_power_kw - r0.net_power_kw) / (m1 - m0)
            if slope == 0:
                break
            m2 = m1 - err / slope
            r0, m0, r1, m1 = r1, m1, solve_point(f, m2, start=r1.states), m2
        if abs(r1.net_power_kw - target_kw) > 0.01 * target_kw:
            raise RuntimeError(
                f"sweep point f={f}: net power "
                f"{r1.net_power_kw / 1000:.1f} MW missed target "
                f"{target_kw / 1000:.1f} MW"
            )
        results.append(r1)
        start = r1.states
    return sorted(results, key=lambda r: r.load_fraction)

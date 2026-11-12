"""Fuel-cost curve fitting.

The sweep gives, at each load point, the standard-coal consumption
``coal_gen`` (g/kWh). The fuel-consumption rate is ``F(P) = coal_gen * P``
in kg/h (numerically: 1 g/kWh at 1 MW is 1 kg/h), and the fuel-cost rate
is ``C(P) = F(P) * coal_price`` with the coal price taken as
1000 CNY/t of standard coal -- the price used in the deep-peak-regulation
benefit analysis of Zhang et al. (2025), Section 5.

Two fits are provided:

- piecewise-linear (the dispatch format): least-squares line per segment,
  segments ``[189, 315, 441, 567, 630] MW`` (breakpoints near 30 / 50 /
  70 / 90 / 100% load);
- quadratic (control): ``F(P) = a P^2 + b P + c``.

Both report the maximum relative error at the sweep points, so the user
can see exactly how much the dispatch curve distorts the simulated one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Standard-coal price, CNY/kg (1000 CNY/t, Zhang et al. 2025, Section 5).
COAL_PRICE_CNY_PER_KG = 1.0

#: Default segment breakpoints, MW (30 / 50 / 70 / 90 / 100% of 630 MW).
DEFAULT_BREAKPOINTS_MW = (189.0, 315.0, 441.0, 567.0, 630.0)


@dataclass
class Segment:
    """One linear piece of the fuel-consumption curve."""

    p_min_mw: float
    p_max_mw: float
    slope_kg_per_h_per_mw: float
    intercept_kg_per_h: float

    @property
    def marginal_cost_cny_per_mwh(self) -> float:
        """Marginal fuel cost of this segment, CNY/MWh."""
        return self.slope_kg_per_h_per_mw * COAL_PRICE_CNY_PER_KG

    def fuel_rate_kg_per_h(self, p_mw: float) -> float:
        return self.slope_kg_per_h_per_mw * p_mw + self.intercept_kg_per_h


@dataclass
class PiecewiseFit:
    segments: list
    max_rel_error: float
    #: Simulated fuel rate at the minimum-load point, kg/h. Anchors the
    #: continuous total-cost construction in :meth:`total_cost_cny_per_h`.
    anchor_fuel_rate_kg_per_h: float = 0.0

    def fuel_rate_kg_per_h(self, p_mw: float) -> float:
        for seg in self.segments:
            if p_mw <= seg.p_max_mw or seg is self.segments[-1]:
                return seg.fuel_rate_kg_per_h(p_mw)
        raise ValueError(f"power {p_mw} MW outside the fitted range")

    def marginal_cost_cny_per_mwh(self, p_mw: float) -> float:
        for seg in self.segments:
            if p_mw <= seg.p_max_mw or seg is self.segments[-1]:
                return seg.marginal_cost_cny_per_mwh
        raise ValueError(f"power {p_mw} MW outside the fitted range")

    def total_cost_cny_per_h(self, p_mw: float) -> float:
        """Continuous total fuel cost, CNY/h.

        The per-segment least-squares lines are discontinuous at the
        breakpoints, so the total cost is built by integrating the
        (monotone) segment slopes from the minimum-load point, anchored at
        the simulated fuel rate there. This is the cost curve the exports
        use; the fixed term is the no-load fuel consumption.
        """
        if p_mw < self.segments[0].p_min_mw - 1e-9:
            raise ValueError(f"power {p_mw} MW below the fitted range")
        total = self.anchor_fuel_rate_kg_per_h * COAL_PRICE_CNY_PER_KG
        prev = self.segments[0].p_min_mw
        for seg in self.segments:
            upper = min(p_mw, seg.p_max_mw)
            if upper > prev:
                total += (
                    seg.slope_kg_per_h_per_mw * (upper - prev) * COAL_PRICE_CNY_PER_KG
                )
            prev = seg.p_max_mw
            if p_mw <= seg.p_max_mw:
                break
        return total


@dataclass
class QuadraticFit:
    a: float  # kg/h per MW^2
    b: float  # kg/h per MW
    c: float  # kg/h
    max_rel_error: float

    def fuel_rate_kg_per_h(self, p_mw: float) -> float:
        return self.a * p_mw**2 + self.b * p_mw + self.c

    def marginal_cost_cny_per_mwh(self, p_mw: float) -> float:
        return (2 * self.a * p_mw + self.b) * COAL_PRICE_CNY_PER_KG


def fuel_rates(power_mw, coal_gen_g_per_kwh):
    """Fuel-consumption rate in kg/h of standard coal."""
    power_mw = np.asarray(power_mw, dtype=float)
    coal = np.asarray(coal_gen_g_per_kwh, dtype=float)
    return coal * power_mw


def _pool_adjacent_violators(slopes, weights):
    """Isotonic regression (non-decreasing) by pool-adjacent-violators."""
    pools = [[s, w, 1] for s, w in zip(slopes, weights)]  # value, weight, count
    i = 0
    while i < len(pools) - 1:
        if pools[i][0] <= pools[i + 1][0]:
            i += 1
            continue
        w = pools[i][1] + pools[i + 1][1]
        v = (pools[i][0] * pools[i][1] + pools[i + 1][0] * pools[i + 1][1]) / w
        pools[i : i + 2] = [[v, w, pools[i][2] + pools[i + 1][2]]]
        if i > 0:
            i -= 1
    out = []
    for value, _w, count in pools:
        out.extend([value] * count)
    return out


def fit_piecewise(
    power_mw,
    fuel_rate_kg_per_h,
    breakpoints=DEFAULT_BREAKPOINTS_MW,
    enforce_monotonic=True,
) -> PiecewiseFit:
    """Least-squares line per segment; returns segments + max rel. error.

    With ``enforce_monotonic`` (default) the segment slopes are pooled
    with isotonic regression so the marginal cost is non-decreasing with
    output -- a convexity requirement for merit-order dispatch. The
    intercepts are then re-fitted per segment with the pooled slope held
    fixed, and the reported error is computed against the final segments.
    """
    p = np.asarray(power_mw, dtype=float)
    f = np.asarray(fuel_rate_kg_per_h, dtype=float)
    raw = []
    for lo, hi in zip(breakpoints[:-1], breakpoints[1:]):
        mask = (p >= lo - 1e-9) & (p <= hi + 1e-9)
        if mask.sum() < 2:
            raise ValueError(f"segment [{lo}, {hi}] MW holds fewer than 2 sweep points")
        slope, intercept = np.polyfit(p[mask], f[mask], 1)
        raw.append([lo, hi, float(slope), float(intercept), int(mask.sum())])
    if enforce_monotonic:
        slopes = _pool_adjacent_violators([r[2] for r in raw], [r[4] for r in raw])
        for row, slope in zip(raw, slopes):
            row[2] = slope
            # Re-fit the intercept with the slope held fixed.
            lo, hi = row[0], row[1]
            mask = (p >= lo - 1e-9) & (p <= hi + 1e-9)
            row[3] = float(np.mean(f[mask] - slope * p[mask]))
    segments = [
        Segment(lo, hi, slope, intercept) for lo, hi, slope, intercept, _n in raw
    ]
    anchor = float(f[np.argmin(p)])
    fit = PiecewiseFit(segments, 0.0, anchor)
    errs = [abs(fit.fuel_rate_kg_per_h(pi) - fi) / fi for pi, fi in zip(p, f)]
    fit.max_rel_error = float(max(errs))
    return fit


def fit_quadratic(power_mw, fuel_rate_kg_per_h) -> QuadraticFit:
    """Quadratic least-squares fit; returns coefficients + max rel. error."""
    p = np.asarray(power_mw, dtype=float)
    f = np.asarray(fuel_rate_kg_per_h, dtype=float)
    a, b, c = np.polyfit(p, f, 2)
    fit = QuadraticFit(float(a), float(b), float(c), 0.0)
    errs = [abs(fit.fuel_rate_kg_per_h(pi) - fi) / fi for pi, fi in zip(p, f)]
    fit.max_rel_error = float(max(errs))
    return fit

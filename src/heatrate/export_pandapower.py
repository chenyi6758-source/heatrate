"""Export the fitted fuel-cost curve to pandapower and run an OPF demo.

Two cost forms are built on the same fitted curve:

- piecewise-linear (``create_pwl_cost``): the points are the *continuous*
  total-cost curve (see :meth:`heatrate.fit.PiecewiseFit.total_cost_cny_per_h`)
  evaluated at the segment breakpoints;
- quadratic (``create_poly_cost``): the coefficients of the quadratic
  control fit.

Costs are in CNY (pandapower names the columns EUR, but the OPF solver
only sees numbers; the currency is documented here and in the README).

The demo network is minimal: one 220 kV bus pair, a 100 MW load, the
heat-rate unit (min 189 MW, max 630 MW) and an expensive external grid,
so the OPF must dispatch the unit. Because the unit's minimum (189 MW)
exceeds the 100 MW load in the demo, the load is set to 400 MW by
default; the export itself imposes no load.
"""

from __future__ import annotations

import pandapower as pp

#: Cost of the external grid in the demo, CNY/MWh (deliberately high).
EXT_GRID_MARGINAL_COST_CNY_PER_MWH = 800.0


def pwl_points(fit):
    """``[[p_lo, p_hi, marginal_cost], ...]`` per segment.

    pandapower's piecewise-linear cost is a list of areas
    ``[p1, p2, c]`` where ``c`` is the (marginal) cost between ``p1``
    and ``p2``; the constant part of the cost function is neglected by
    the OPF, so only the segment slopes matter here.
    """
    return [
        [seg.p_min_mw, seg.p_max_mw, seg.marginal_cost_cny_per_mwh]
        for seg in fit.segments
    ]


def build_network(fit, quadratic_fit=None, load_mw: float = 400.0, cost: str = "pwl"):
    """Build the two-bus demo network with the fitted cost curve.

    Parameters
    ----------
    cost:
        ``"pwl"`` for the piecewise-linear cost, ``"poly"`` for the
        quadratic cost (needs ``quadratic_fit``).
    """
    if cost not in ("pwl", "poly"):
        raise ValueError('cost must be "pwl" or "poly"')
    if cost == "poly" and quadratic_fit is None:
        raise ValueError("quadratic_fit is required for cost='poly'")
    p_min = fit.segments[0].p_min_mw
    p_max = fit.segments[-1].p_max_mw
    net = pp.create_empty_network()
    b0 = pp.create_bus(net, vn_kv=220.0)
    b1 = pp.create_bus(net, vn_kv=220.0)
    # OPF-solver notes (verified against pandapower 3.5.6 / PYPOWER MIPS
    # in this environment, no PIPS installed):
    # - the external grid must have min_p_mw = 0: without it the solver
    #   "sells" surplus power back to the grid (negative dispatch) to
    #   exploit the grid's linear cost, which is not the intended demo;
    # - explicit tight reactive-power limits are set on the grid and the
    #   generator: the defaults (+/-1e9 MVAr) make MIPS fail outright.
    pp.create_ext_grid(
        net, bus=b0, vm_pu=1.0, min_p_mw=0.0, min_q_mvar=-500.0, max_q_mvar=500.0
    )
    pp.create_line_from_parameters(
        net,
        from_bus=b0,
        to_bus=b1,
        length_km=10.0,
        r_ohm_per_km=0.02,
        x_ohm_per_km=0.08,
        c_nf_per_km=0.0,
        max_i_ka=2.0,
    )
    pp.create_load(net, bus=b1, p_mw=load_mw)
    gen = pp.create_gen(
        net,
        bus=b1,
        p_mw=load_mw,
        vm_pu=1.0,
        min_p_mw=p_min,
        max_p_mw=p_max,
        min_q_mvar=-200.0,
        max_q_mvar=200.0,
    )
    if cost == "pwl":
        pp.create_pwl_cost(net, element=gen, et="gen", points=pwl_points(fit))
    else:
        pp.create_poly_cost(
            net,
            element=gen,
            et="gen",
            cp1_eur_per_mw=quadratic_fit.b,
            cp2_eur_per_mw2=quadratic_fit.a,
            cp0_eur=quadratic_fit.c,
        )
    pp.create_poly_cost(
        net, element=0, et="ext_grid", cp1_eur_per_mw=EXT_GRID_MARGINAL_COST_CNY_PER_MWH
    )
    return net


def run_opf(fit, quadratic_fit=None, load_mw: float = 400.0, cost: str = "pwl"):
    """Run the OPF demo and return ``(gen_MW, ext_grid_MW, converged)``."""
    net = build_network(fit, quadratic_fit, load_mw=load_mw, cost=cost)
    pp.runopp(net, verbose=False)
    gen_mw = float(net.res_gen.p_mw.iloc[0])
    ext_mw = float(net.res_ext_grid.p_mw.iloc[0])
    return gen_mw, ext_mw, bool(net.OPF_converged)

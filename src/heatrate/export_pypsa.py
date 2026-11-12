"""Export the fitted fuel-cost curve to PyPSA and run a LOPF demo.

PyPSA has no native piecewise marginal cost for a single generator, so
the curve is represented the standard way: one generator per segment.
The minimum stable load (189 MW, 30% of rated) is a must-run base block
-- a generator with ``p_min_pu = 1`` at the average cost of the
minimum-load point -- and each segment above it is a generator with
``p_nom`` equal to the segment width and ``marginal_cost`` equal to the
segment slope (monotone by construction, see :mod:`heatrate.fit`).

Costs are in CNY/MWh (the coal price is 1000 CNY/t of standard coal);
PyPSA's ``marginal_cost`` column is currency-agnostic, so the numbers
are used as-is and the currency is documented here and in the README.

The demo network is deliberately minimal: one heat-rate unit plus an
expensive peaking generator on a two-bus system, solved with HiGHS
through PyPSA's LOPF. It verifies that the unit is dispatched in merit
order and that its minimum-load block is respected.
"""

from __future__ import annotations

import pypsa

#: Marginal cost of the peaking generator in the demo, CNY/MWh.
PEAKER_MARGINAL_COST_CNY_PER_MWH = 800.0
#: Nameplate of the peaking generator, MW.
PEAKER_P_NOM_MW = 500.0


def segment_generators(fit):
    """Return ``[(name, p_nom_mw, marginal_cost), ...]`` per segment."""
    rows = []
    for i, seg in enumerate(fit.segments):
        rows.append(
            (
                f"heatrate_seg{i + 1}",
                seg.p_max_mw - seg.p_min_mw,
                seg.marginal_cost_cny_per_mwh,
            )
        )
    return rows


def base_block(fit):
    """Minimum-load block: (p_nom_mw, marginal_cost_cny_per_mwh)."""
    p_min = fit.segments[0].p_min_mw
    avg_cost = fit.anchor_fuel_rate_kg_per_h / p_min  # CNY/MWh, price 1/kg
    return p_min, avg_cost


def build_network(fit, load_mw: float = 400.0):
    """Build the two-bus demo network with the fitted cost curve."""
    p_min, base_cost = base_block(fit)
    net = pypsa.Network()
    net.add("Bus", "gen_bus", v_nom=220.0)
    net.add("Bus", "load_bus", v_nom=220.0)
    net.add("Line", "line", bus0="gen_bus", bus1="load_bus", x=0.01, s_nom=1000.0)
    net.add(
        "Generator",
        "heatrate_base",
        bus="gen_bus",
        p_nom=p_min,
        p_min_pu=1.0,
        marginal_cost=base_cost,
        control="PV",
    )
    for name, width, cost in segment_generators(fit):
        net.add(
            "Generator",
            name,
            bus="gen_bus",
            p_nom=width,
            p_min_pu=0.0,
            marginal_cost=cost,
            control="PV",
        )
    net.add(
        "Generator",
        "peaker",
        bus="gen_bus",
        p_nom=PEAKER_P_NOM_MW,
        p_min_pu=0.0,
        marginal_cost=PEAKER_MARGINAL_COST_CNY_PER_MWH,
        control="PV",
    )
    net.add("Load", "load", bus="load_bus", p_set=load_mw)
    return net


def run_lopf(fit, load_mw: float = 400.0, solver_name: str = "highs"):
    """Run the LOPF demo and return ``{generator: dispatched MW}``.

    Raises ``RuntimeError`` if the optimisation is not optimal (e.g. a
    load below the 189 MW minimum stable load makes the problem
    infeasible, which is itself the minimum-load constraint at work).
    """
    net = build_network(fit, load_mw=load_mw)
    net.optimize(solver_name=solver_name, include_objective_constant=False)
    status = net.model.status
    if str(status) != "ok":
        raise RuntimeError(f"LOPF did not solve to optimality: {status}")
    dispatch = {g: float(net.generators_t.p[g].iloc[0]) for g in net.generators.index}
    return dispatch


def heatrate_dispatch_mw(dispatch: dict) -> float:
    """Total dispatched power of the heat-rate unit (base + segments)."""
    return sum(v for k, v in dispatch.items() if k.startswith("heatrate"))

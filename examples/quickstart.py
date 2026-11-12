"""Quickstart: calibrate the 630 MW design point, sweep 30%-100% load,
fit the fuel-cost curve, and run the PyPSA / pandapower dispatch demos.

Run from the repository root: ``python examples/quickstart.py``.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from heatrate import calibrate_design
from heatrate.cli import _interp_hr
from heatrate.data import TEST_HEAT_RATE_KJ_PER_KWH, THA_HEAT_RATE_KJ_PER_KWH
from heatrate.export_pandapower import run_opf
from heatrate.export_pypsa import heatrate_dispatch_mw, run_lopf
from heatrate.fit import fit_piecewise, fit_quadratic, fuel_rates
from heatrate.offdesign import sweep
from heatrate.report import format_sweep_table


def main() -> None:
    design = calibrate_design()
    print(
        f"design point: main steam {design.main_steam_flow_kg_per_s:.1f} "
        f"kg/s ({design.main_steam_flow_kg_per_s * 3.6:.1f} t/h), "
        f"net {design.net_power_kw / 1000:.1f} MW, "
        f"steam-side heat rate {design.heat_rate_steam:.1f} kJ/kWh, "
        f"standard-coal {design.coal_gen_g_per_kwh:.1f} g/kWh"
    )
    print(f"energy-balance residual: {design.energy_balance_residual_kw:.2f} kW")
    print()

    rows = sweep(design=design)
    print(format_sweep_table(rows))
    print()

    p = [r.net_power_kw / 1000.0 for r in rows]
    f = fuel_rates(p, [r.coal_gen_g_per_kwh for r in rows])
    pw = fit_piecewise(p, f)
    quad = fit_quadratic(p, f)
    print(
        f"piecewise-linear fit (4 segments): max rel. error "
        f"{pw.max_rel_error * 100:.3f}%"
    )
    for seg in pw.segments:
        print(
            f"  {seg.p_min_mw:.0f}-{seg.p_max_mw:.0f} MW: "
            f"{seg.marginal_cost_cny_per_mwh:.1f} CNY/MWh"
        )
    print(
        f"quadratic fit: max rel. error {quad.max_rel_error * 100:.3f}%, "
        f"a={quad.a:.5f} b={quad.b:.2f} c={quad.c:.0f}"
    )
    print()

    print("validation against N630 (Zhang et al. 2025):")
    for frac, measured in sorted(THA_HEAT_RATE_KJ_PER_KWH.items()):
        model = _interp_hr(rows, frac * 630.0)
        print(
            f"  {frac * 630:5.0f} MW THA design: model {model:.1f} vs "
            f"{measured:.1f} kJ/kWh ({(model - measured) / measured * 100:+.2f}%)"
        )
    for load_mw, measured in sorted(TEST_HEAT_RATE_KJ_PER_KWH.items()):
        if load_mw < rows[0].net_power_kw / 1000.0:
            continue
        model = _interp_hr(rows, load_mw)
        print(
            f"  {load_mw:5.0f} MW test measured: model {model:.1f} vs "
            f"{measured:.1f} kJ/kWh ({(model - measured) / measured * 100:+.2f}%)"
        )
    print()

    dispatch = run_lopf(pw, load_mw=400.0)
    print(
        f"PyPSA LOPF at 400 MW load: heat-rate unit "
        f"{heatrate_dispatch_mw(dispatch):.1f} MW, "
        f"peaker {dispatch['peaker']:.1f} MW"
    )
    dispatch = run_lopf(pw, load_mw=700.0)
    print(
        f"PyPSA LOPF at 700 MW load: heat-rate unit "
        f"{heatrate_dispatch_mw(dispatch):.1f} MW, "
        f"peaker {dispatch['peaker']:.1f} MW"
    )
    for cost in ("pwl", "poly"):
        gen, ext, ok = run_opf(pw, quad, load_mw=400.0, cost=cost)
        print(
            f"pandapower OPF ({cost}) at 400 MW load: unit {gen:.1f} MW, "
            f"ext. grid {ext:.1f} MW, converged={ok}"
        )


if __name__ == "__main__":
    main()

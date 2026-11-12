"""Command-line interface: ``heatrate sweep|export|validate``."""

from __future__ import annotations

import argparse
import sys

from . import calibrate_design
from .data import TEST_HEAT_RATE_KJ_PER_KWH, THA_HEAT_RATE_KJ_PER_KWH
from .export_pandapower import run_opf
from .export_pypsa import heatrate_dispatch_mw, run_lopf
from .fit import fit_piecewise, fit_quadratic, fuel_rates
from .offdesign import sweep
from .report import format_sweep_table, format_validation_table, write_json

DEFAULT_FRACTIONS = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3)


def _load_rows(fractions):
    design = calibrate_design()
    return sweep(fractions, design=design)


def _fits(rows):
    p = [r.net_power_kw / 1000.0 for r in rows]
    f = fuel_rates(p, [r.coal_gen_g_per_kwh for r in rows])
    return fit_piecewise(p, f), fit_quadratic(p, f)


def _interp_hr(rows, load_mw: float) -> float:
    pts = sorted((r.net_power_kw / 1000.0, r.heat_rate_steam) for r in rows)
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    if load_mw <= xs[0]:
        return ys[0]
    if load_mw >= xs[-1]:
        return ys[-1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= load_mw <= x1:
            return y0 + (y1 - y0) * (load_mw - x0) / (x1 - x0)
    raise ValueError("interpolation failed")


def cmd_sweep(args) -> int:
    fractions = tuple(float(x) for x in args.fractions.split(","))
    rows = _load_rows(fractions)
    print(format_sweep_table(rows))
    if args.json:
        write_json(rows, args.json)
        print(f"wrote {args.json}")
    return 0


def cmd_export(args) -> int:
    rows = _load_rows(DEFAULT_FRACTIONS)
    pw, quad = _fits(rows)
    print(f"piecewise fit max rel. error: {pw.max_rel_error * 100:.3f}%")
    print(f"quadratic fit max rel. error: {quad.max_rel_error * 100:.3f}%")
    for seg in pw.segments:
        print(
            f"  {seg.p_min_mw:.0f}-{seg.p_max_mw:.0f} MW: marginal cost "
            f"{seg.marginal_cost_cny_per_mwh:.1f} CNY/MWh"
        )
    if args.format == "pypsa":
        dispatch = run_lopf(pw, load_mw=args.load)
        total = heatrate_dispatch_mw(dispatch)
        print(
            f"PyPSA LOPF at {args.load:.0f} MW load: heat-rate unit "
            f"dispatches {total:.1f} MW"
        )
        for name, mw in sorted(dispatch.items()):
            print(f"  {name}: {mw:.1f} MW")
    else:
        gen, ext, ok = run_opf(pw, quad, load_mw=args.load, cost=args.cost)
        print(
            f"pandapower OPF ({args.cost}) at {args.load:.0f} MW load: "
            f"unit {gen:.1f} MW, ext. grid {ext:.1f} MW, "
            f"converged={ok}"
        )
    return 0


def cmd_validate(args) -> int:
    rows = _load_rows(DEFAULT_FRACTIONS)
    comparison = []
    for frac, measured in sorted(THA_HEAT_RATE_KJ_PER_KWH.items()):
        load_mw = frac * 630.0
        model = _interp_hr(rows, load_mw)
        comparison.append(
            {
                "load_mw": load_mw,
                "model_hr": model,
                "measured_hr": measured,
                "deviation_pct": (model - measured) / measured * 100.0,
                "basis": "THA design",
            }
        )
    for load_mw, measured in sorted(TEST_HEAT_RATE_KJ_PER_KWH.items()):
        if load_mw > 630.0 or load_mw < rows[0].net_power_kw / 1000.0:
            print(
                f"  {load_mw:.0f} MW test point is outside the sweep "
                f"range, skipped (no extrapolation)"
            )
            continue
        model = _interp_hr(rows, load_mw)
        comparison.append(
            {
                "load_mw": load_mw,
                "model_hr": model,
                "measured_hr": measured,
                "deviation_pct": (model - measured) / measured * 100.0,
                "basis": "test measured",
            }
        )
    print(format_validation_table(comparison))
    worst = max(abs(c["deviation_pct"]) for c in comparison)
    print(f"largest absolute deviation: {worst:.2f}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="heatrate",
        description="Heat-rate curve generator for coal-fired units: "
        "TESPy cycle, load sweep, PyPSA/pandapower cost export.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("sweep", help="sweep the load range and print the table")
    ps.add_argument(
        "--fractions",
        default=",".join(map(str, DEFAULT_FRACTIONS)),
        help="comma-separated load fractions (default: 1.0,...,0.3)",
    )
    ps.add_argument("--json", default=None, help="write the sweep as JSON")
    ps.set_defaults(func=cmd_sweep)

    pe = sub.add_parser("export", help="fit the cost curve and run a dispatch demo")
    pe.add_argument("--format", choices=["pypsa", "pandapower"], required=True)
    pe.add_argument(
        "--cost",
        choices=["pwl", "poly"],
        default="pwl",
        help="pandapower cost form (default: pwl)",
    )
    pe.add_argument("--load", type=float, default=400.0, help="demo load, MW")
    pe.set_defaults(func=cmd_export)

    pv = sub.add_parser("validate", help="compare the model heat rate with N630 data")
    pv.set_defaults(func=cmd_validate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

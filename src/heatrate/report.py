"""Text and JSON reporting for sweep results."""

from __future__ import annotations

import json

from .data import REFERENCE

HEADER = (
    "load%   P(MW)  m(kg/s) p_ms(bar) fwT(C)  HR_steam  HR_fuel  eta_cyc "
    " eta_b  coal_g  coal_s"
)


def format_sweep_table(rows) -> str:
    lines = [HEADER]
    for r in rows:
        lines.append(
            f"{r.load_fraction * 100:5.0f}%  {r.net_power_kw / 1000:6.1f}  "
            f"{r.main_steam_flow_kg_per_s:7.1f}  "
            f"{r.main_steam_pressure_bar:8.1f}  {r.feedwater_temp_c:6.1f}  "
            f"{r.heat_rate_steam:8.1f}  {r.heat_rate_fuel:7.1f}  "
            f"{r.cycle_efficiency:7.4f}  {r.boiler_efficiency:6.4f}  "
            f"{r.coal_gen_g_per_kwh:6.1f}  {r.coal_supply_g_per_kwh:6.1f}"
        )
    return "\n".join(lines)


def format_validation_table(comparison) -> str:
    """``comparison``: list of dicts with load_mw / model / measured / dev%."""
    lines = [
        "load(MW)  model HR  measured HR  deviation  basis",
    ]
    for row in comparison:
        lines.append(
            f"{row['load_mw']:8.0f}  {row['model_hr']:8.1f}  "
            f"{row['measured_hr']:11.1f}  {row['deviation_pct']:+9.2f}%  "
            f"{row['basis']}"
        )
    return "\n".join(lines)


def rows_to_json(rows) -> str:
    out = []
    for r in rows:
        d = {k: v for k, v in r.__dict__.items() if k != "states"}
        out.append(d)
    return json.dumps(
        {"reference": REFERENCE, "rows": out}, indent=2, ensure_ascii=False
    )


def write_json(rows, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(rows_to_json(rows) + "\n")

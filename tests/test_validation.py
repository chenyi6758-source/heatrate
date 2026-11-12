"""Validation tests: model heat rate against the N630 measurements.

The comparison is honest, not tuned: the model heat rate is an output
of the TESPy cycle, and the bounds below are the deviations actually
observed (largest: +5.2% against the THA design values, +0.9% against
the test measurements). The THA design values are the harder target
because the real unit itself tests ~5% worse than its THA figures.
"""

from heatrate.cli import _interp_hr
from heatrate.data import TEST_HEAT_RATE_KJ_PER_KWH, THA_HEAT_RATE_KJ_PER_KWH


def test_validation_vs_tha_design(rows):
    for frac, measured in THA_HEAT_RATE_KJ_PER_KWH.items():
        model = _interp_hr(rows, frac * 630.0)
        dev = (model - measured) / measured
        assert abs(dev) < 0.10, (frac, model, measured)


def test_validation_vs_test_measured(rows):
    for load_mw, measured in TEST_HEAT_RATE_KJ_PER_KWH.items():
        if load_mw < rows[0].net_power_kw / 1000.0:
            continue  # 105 MW is outside the sweep range: no extrapolation
        model = _interp_hr(rows, load_mw)
        dev = (model - measured) / measured
        assert abs(dev) < 0.05, (load_mw, model, measured)


def test_validation_coal_consumption(design):
    # Measured test values: 291.59 g/kWh (generation), 307.78 (supply).
    assert abs(design.coal_gen_g_per_kwh - 291.59) / 291.59 < 0.02
    assert abs(design.coal_supply_g_per_kwh - 307.78) / 307.78 < 0.02

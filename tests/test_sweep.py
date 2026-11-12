"""Sweep tests: monotonicity and low-load deterioration."""


def test_sweep_monotone_heat_rate(rows):
    hrs = [r.heat_rate_steam for r in rows]  # ascending load order
    for lo, hi in zip(hrs, hrs[1:]):
        assert hi < lo, "heat rate must fall as load rises"


def test_sweep_monotone_efficiency(rows):
    effs = [r.cycle_efficiency for r in rows]
    for lo, hi in zip(effs, effs[1:]):
        assert hi > lo, "cycle efficiency must rise as load rises"


def test_sweep_low_load_deterioration_accelerates(rows):
    by_f = {round(r.load_fraction, 2): r for r in rows}
    rise_high = by_f[0.80].heat_rate_steam - by_f[1.00].heat_rate_steam
    rise_low = by_f[0.30].heat_rate_steam - by_f[0.50].heat_rate_steam
    assert rise_low > rise_high
    # Overall deterioration 100% -> 30% is material but bounded.
    assert 500.0 < by_f[0.30].heat_rate_steam - by_f[1.00].heat_rate_steam < 1500.0


def test_sweep_all_points_converged_and_physical(rows):
    assert len(rows) == 8
    for r in rows:
        assert r.converged is True
        assert abs(r.energy_balance_residual_kw) < 1.0
        assert r.extraction_hp_kg_per_s > 0
        assert r.extraction_ip_kg_per_s > 0
        assert r.extraction_lp_kg_per_s > 0
        assert abs(r.net_power_kw / 1000.0 - r.load_fraction * 630.0) < 2.0


def test_sweep_coal_consumption_rises_at_low_load(rows):
    by_f = {round(r.load_fraction, 2): r for r in rows}
    assert by_f[0.30].coal_gen_g_per_kwh > by_f[1.00].coal_gen_g_per_kwh
    assert by_f[0.30].coal_supply_g_per_kwh > by_f[1.00].coal_supply_g_per_kwh

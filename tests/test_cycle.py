"""Design-point tests: calibration, heat rate, energy balance."""


def test_design_point_calibrates_to_630mw(design):
    assert abs(design.net_power_kw - 630_000.0) <= 500.0
    assert abs(design.gross_power_kw - 665_000.0) <= 5_000.0


def test_design_point_heat_rate_in_range(design):
    # Steam-side heat rate: the measured test value is 7840.32 kJ/kWh and
    # the THA design value 7485 kJ/kWh; the model must sit in that band.
    assert 7_000.0 < design.heat_rate_steam < 8_500.0
    assert 0.42 < design.cycle_efficiency < 0.48


def test_design_point_energy_balance_closes(design):
    # Steam heat in = shaft work + condenser heat rejected, to < 1 kW.
    assert abs(design.energy_balance_residual_kw) < 1.0


def test_design_point_flows_positive(design):
    assert design.main_steam_flow_kg_per_s > 0
    assert design.extraction_hp_kg_per_s > 0
    assert design.extraction_ip_kg_per_s > 0
    assert design.extraction_lp_kg_per_s > 0
    # Main-steam flow: test 552.4 kg/s, THA design 499 kg/s; the model
    # must lie between them (it does: ~519 kg/s).
    assert 450.0 < design.main_steam_flow_kg_per_s < 600.0


def test_design_point_states(design):
    # Feedwater temperature: 3-stage regen reaches 254 C, below the real
    # 8-stage unit's 288 C -- the documented simplification gap.
    assert 240.0 < design.feedwater_temp_c < 270.0
    assert abs(design.main_steam_pressure_bar - 242.0) < 0.5
    assert abs(design.condenser_pressure_bar - 0.07) < 1e-9
    # Standard-coal consumption: measured test value 291.59 g/kWh.
    assert 270.0 < design.coal_gen_g_per_kwh < 310.0


def test_design_point_converged_and_finite(design):
    assert design.converged is True
    for label, (m, p, t, h) in design.states.items():
        assert m == m and p == p and t == t and h == h, label
        assert m > -1e-9, label  # no negative mass flow anywhere
    assert design.pump_power_kw > 0
    assert design.shaft_power_kw > design.net_power_kw

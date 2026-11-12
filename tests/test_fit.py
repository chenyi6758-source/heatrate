"""Fit tests: accuracy and dispatch-safe (monotone) slopes."""


def test_piecewise_fit_accuracy(piecewise, rows):
    assert piecewise.max_rel_error < 0.01
    for seg in piecewise.segments:
        assert seg.p_min_mw < seg.p_max_mw


def test_piecewise_slopes_monotone(piecewise):
    slopes = [s.slope_kg_per_h_per_mw for s in piecewise.segments]
    for lo, hi in zip(slopes, slopes[1:]):
        assert hi >= lo, "marginal cost must not fall with output"


def test_piecewise_total_cost_matches_simulation(piecewise, rows):
    # The continuous export curve must track the simulated fuel rates.
    for r in rows:
        p = r.net_power_kw / 1000.0
        simulated = r.coal_gen_g_per_kwh * p
        fitted = piecewise.total_cost_cny_per_h(p)
        assert abs(fitted - simulated) / simulated < 0.01


def test_piecewise_anchor(piecewise):
    # Total cost at minimum load equals the simulated fuel rate there.
    assert (
        abs(piecewise.total_cost_cny_per_h(189.0) - piecewise.anchor_fuel_rate_kg_per_h)
        < 1.0
    )


def test_quadratic_fit_accuracy(quadratic):
    assert quadratic.max_rel_error < 0.01
    assert quadratic.a > 0  # convex: marginal cost rises with output


def test_quadratic_marginal_cost_rises(quadratic):
    assert quadratic.marginal_cost_cny_per_mwh(
        630.0
    ) > quadratic.marginal_cost_cny_per_mwh(189.0)

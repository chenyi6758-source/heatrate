"""Shared fixtures: one calibration + one sweep per test session."""

import pytest

from heatrate import calibrate_design
from heatrate.fit import fit_piecewise, fit_quadratic, fuel_rates
from heatrate.offdesign import sweep


@pytest.fixture(scope="session")
def design():
    return calibrate_design()


@pytest.fixture(scope="session")
def rows(design):
    return sweep(design=design)


@pytest.fixture(scope="session")
def fits(rows):
    p = [r.net_power_kw / 1000.0 for r in rows]
    f = fuel_rates(p, [r.coal_gen_g_per_kwh for r in rows])
    return fit_piecewise(p, f), fit_quadratic(p, f)


@pytest.fixture(scope="session")
def piecewise(fits):
    return fits[0]


@pytest.fixture(scope="session")
def quadratic(fits):
    return fits[1]

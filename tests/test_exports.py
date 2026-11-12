"""Export tests: PyPSA LOPF and pandapower OPF dispatch the fitted curve."""

import pytest

from heatrate.export_pandapower import run_opf
from heatrate.export_pypsa import heatrate_dispatch_mw, run_lopf


def test_pypsa_lopf_mid_load(piecewise):
    dispatch = run_lopf(piecewise, load_mw=400.0)
    assert abs(heatrate_dispatch_mw(dispatch) - 400.0) < 1.0
    assert abs(dispatch["peaker"]) < 1.0
    assert abs(dispatch["heatrate_base"] - 189.0) < 1e-6
    # The two most expensive segments stay empty while cheaper
    # capacity remains.
    assert abs(dispatch["heatrate_seg3"]) < 1e-6
    assert abs(dispatch["heatrate_seg4"]) < 1e-6


def test_pypsa_lopf_high_load(piecewise):
    dispatch = run_lopf(piecewise, load_mw=700.0)
    assert abs(heatrate_dispatch_mw(dispatch) - 630.0) < 1.0
    assert abs(dispatch["peaker"] - 70.0) < 1.0


def test_pypsa_lopf_below_min_load_is_infeasible(piecewise):
    # A 150 MW load cannot be served by a unit whose minimum stable load
    # is 189 MW; the LOPF must report that instead of dispatching
    # something unphysical.
    with pytest.raises(RuntimeError):
        run_lopf(piecewise, load_mw=150.0)


@pytest.mark.parametrize("cost", ["pwl", "poly"])
@pytest.mark.parametrize(
    "load_mw, expected_gen, expected_ext", [(400.0, 400.0, 0.0), (700.0, 630.0, 70.0)]
)
def test_pandapower_opf(
    piecewise, quadratic, cost, load_mw, expected_gen, expected_ext
):
    gen, ext, ok = run_opf(piecewise, quadratic, load_mw=load_mw, cost=cost)
    assert ok is True
    assert abs(gen - expected_gen) < 2.0
    assert abs(ext - expected_ext) < 2.0

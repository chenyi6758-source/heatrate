"""heatrate: heat-rate curve generator for coal-fired units.

Build a TESPy model of a supercritical reheat regenerative coal unit,
sweep the load range, and export the fuel-cost curve for PyPSA and
pandapower unit-commitment / optimal-power-flow studies.
"""

from .cycle import DesignResult, calibrate_design, solve_point
from .offdesign import aux_rate, boiler_efficiency, sweep, turbine_eta_s

__version__ = "0.1.0"
__all__ = [
    "DesignResult",
    "calibrate_design",
    "solve_point",
    "sweep",
    "turbine_eta_s",
    "boiler_efficiency",
    "aux_rate",
]

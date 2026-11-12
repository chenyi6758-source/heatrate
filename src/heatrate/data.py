"""Measured reference data for the N630-24.2/566/566 supercritical unit.

All numbers are taken from Zhang et al. (2025), "Thermal economy analysis
on deep peak regulation operation of supercritical 630 MW coal-fired unit",
*Frontiers in Energy Research* 13:1611001,
DOI 10.3389/fenrg.2025.1611001 (open access, published 2025-10-16).

Two different heat-rate series appear in the paper and must not be mixed:

- **THA design values** (Table 1): 7485 / 7604 / 7920 kJ/kWh at 100% / 75% /
  50% THA. These are the turbine heat-acceptance design figures.
- **Test-measured values** (Section 4.2, Figure 4): 7840.32 kJ/kWh at 630 MW,
  8409.82 kJ/kWh at 300 MW, 9340 kJ/kWh at 105 MW. The paper's "heat rate"
  is the *steam-side turbine heat rate*: heat absorbed by the steam in the
  boiler and reheater divided by the generator power output, i.e.
  ``HR = (Q_boiler + Q_reheat) / P_gross``. The "absolute electrical
  efficiency" quoted in the paper is exactly ``3600 / HR`` (e.g.
  3600 / 9340 = 38.54%), confirming that HR is steam-side, not fuel-based.
  The fuel-based standard-coal consumption follows as
  ``b = HR / (eta_boiler * eta_piping * 29.27 MJ/kg)`` with a piping
  efficiency of 0.99 (the paper's formula); e.g. at 105 MW,
  9340 / (0.8961 * 0.99 * 29.27) = 359.7 g/kWh, matching the reported
  359.25 g/kWh.

``heatrate`` therefore validates its **steam-side** heat rate against the
paper's heat rate, and computes fuel-based figures with the same
boiler/piping-efficiency convention.
"""

from __future__ import annotations

DOI = "10.3389/fenrg.2025.1611001"
REFERENCE = (
    "Zhang et al. (2025), 'Thermal economy analysis on deep peak "
    "regulation operation of supercritical 630 MW coal-fired unit', "
    "Front. Energy Res. 13:1611001, DOI " + DOI
)

#: Standard-coal lower heating value, MJ/kg (Chinese convention).
LHV_STANDARD_COAL_MJ_PER_KG = 29.27
#: Piping efficiency used in the paper's coal-consumption formula.
PIPING_EFFICIENCY = 0.99

#: Design (THA) heat rates, kJ/kWh, Table 1 of the paper.
THA_HEAT_RATE_KJ_PER_KWH = {1.00: 7485.0, 0.75: 7604.0, 0.50: 7920.0}

#: Test-measured steam-side heat rates, kJ/kWh (Section 4.2 / Figure 4).
#: Keys are unit load in MW.
TEST_HEAT_RATE_KJ_PER_KWH = {630.0: 7840.32, 300.0: 8409.82, 105.0: 9340.0}

#: Test-measured boiler efficiency (Section 4.1 / Figure 2).
#: Keys are unit load in MW. The maximum, 93.58%, occurs at 475 MW; the
#: paper does not state the 630 MW value.
TEST_BOILER_EFFICIENCY = {475.0: 0.9358, 240.0: 0.9279, 105.0: 0.8961}

#: Test-measured plant (auxiliary) power rate (Section 4.3 / Figure 5).
TEST_AUX_RATE = {630.0: 0.0526, 475.0: 0.0463, 300.0: 0.0508, 105.0: 0.1222}

#: Test-measured standard-coal consumption for power generation, g/kWh.
TEST_COAL_GEN_G_PER_KWH = {630.0: 291.59, 300.0: 312.21, 105.0: 359.25}

#: Test-measured standard-coal consumption for power supply, g/kWh.
TEST_COAL_SUPPLY_G_PER_KWH = {630.0: 307.78, 300.0: 328.92, 105.0: 409.26}

#: Test-measured main-steam flow, t/h (Table 2).
TEST_MAIN_STEAM_FLOW_T_PER_H = {
    630.0: 1988.63,
    475.0: 1439.47,
    300.0: 890.66,
    240.0: 702.48,
    180.0: 519.09,
    140.0: 406.51,
    105.0: 312.62,
}

#: Test-measured main-steam pressure, MPa (Table 2).
TEST_MAIN_STEAM_PRESSURE_MPA = {
    630.0: 23.98,
    475.0: 22.48,
    300.0: 15.77,
    240.0: 13.30,
    180.0: 10.32,
    140.0: 9.65,
    105.0: 9.43,
}

#: Test-measured final feedwater temperature, degC (Table 2).
TEST_FEEDWATER_TEMP_C = {
    630.0: 288.3,
    475.0: 269.5,
    300.0: 244.3,
    240.0: 231.7,
    180.0: 217.6,
    140.0: 204.7,
    105.0: 194.9,
}

#: Design (THA) parameters, Table 1 of the paper.
THA_DESIGN = {
    "main_steam_pressure_mpa": 24.20,
    "main_steam_temp_c": 566.0,
    "hp_exhaust_pressure_mpa": 4.666,
    "hp_exhaust_temp_c": 321.0,
    "reheat_pressure_mpa": 4.199,
    "reheat_temp_c": 566.0,
    "ip_exhaust_pressure_mpa": 1.131,
    "ip_exhaust_temp_c": 368.6,
    "exhaust_pressure_kpa": 4.9,
    "feedwater_temp_c": 285.9,
    "main_steam_flow_t_per_h": 1796.4,
    "hp_cylinder_efficiency": 0.8734,
    "ip_cylinder_efficiency": 0.9261,
}

#: Test-measured cylinder efficiencies at 630 MW (Section 4.2 / Figure 3).
#: HP cylinder: 84.12% at 630 MW, falling to 69.15% at 105 MW (non-monotonic
#: because of regulating-valve sequencing); IP: 87.86% -> 86.25%;
#: LP: 85.86% -> 79.58%.
TEST_CYLINDER_EFFICIENCY_630MW = {"hp": 0.8412, "ip": 0.8786, "lp": 0.8586}
TEST_CYLINDER_EFFICIENCY_105MW = {"hp": 0.6915, "ip": 0.8625, "lp": 0.7958}

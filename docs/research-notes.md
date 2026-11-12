# heatrate — research notes

## The problem

A power-system researcher or student who wants a fuel-cost curve for a
coal unit in a PyPSA or pandapower unit-commitment study today has two
bad options: type in a textbook quadratic by hand, or copy a "typical"
heat rate from a handbook. Neither is traceable to a thermodynamic
model, and neither shows how fast the heat rate deteriorates at low
load — the exact quantity that decides whether deep peak shaving pays.
The heat-rate curve should come out of a heat-balance model, not out
of a table.

## Literature (verified)

### Zhang et al. (2025) — the validation set

Zhang et al., "Thermal economy analysis on deep peak regulation
operation of supercritical 630 MW coal-fired unit", *Frontiers in
Energy Research* 13:1611001, DOI 10.3389/fenrg.2025.1611001
(open access, 2025-10-16). A wide-load test of a real N630-24.2/566/566
unit at 630 / 475 / 300 / 240 / 180 / 140 / 105 MW. Verified facts used
here (all read from the paper, not from secondary sources):

- THA design heat rates: 7485 (100%) / 7604 (75%) / 7920 (50%) kJ/kWh.
- Test-measured heat rates: 7840.32 (630 MW) / 8409.82 (300 MW) /
  9340 (105 MW) kJ/kWh. The paper's "heat rate" is the **steam-side
  turbine heat rate** — heat absorbed by the steam in boiler +
  reheater per kWh generated — and its "absolute electrical efficiency"
  is exactly 3600 / HR (e.g. 3600 / 9340 = 38.54% at 105 MW).
- Boiler efficiency: maximum 93.58% at 475 MW, 92.79% at 240 MW,
  89.61% at 105 MW (the 630 MW value is not stated).
- Plant power rate: 5.26% (630 MW), 4.63% (475 MW), 5.08% (300 MW),
  12.22% (105 MW).
- Standard-coal consumption (generation): 291.59 (630 MW), 312.21
  (300 MW), 359.25 (105 MW) g/kWh; the coal formula is
  `b = HR / (eta_boiler * eta_piping * 29.27 MJ/kg)` with piping
  efficiency 0.99 — it reproduces the reported 359.25 g/kWh at 105 MW.
- Cylinder efficiencies at 630 MW (test): HP 84.12%, IP 87.86%, LP
  85.86%; at 105 MW: HP 69.15%, IP 86.25%, LP 79.58%. The HP
  cylinder's drop is large and **non-monotonic** (77.15% at 240 MW,
  back up to 80.24% at 180 MW) because of regulating-valve sequencing.
- Main-steam flow: 1988.63 t/h at 630 MW (552.4 kg/s); THA design
  1796.4 t/h (499 kg/s). Main-steam pressure (test): 23.98 MPa at
  630 MW, 22.48 at 475 MW, 15.77 at 300 MW — i.e. the pressure falls
  *less* steeply than the load (valve throttling at high load), while
  this project's Stodola approximation scales pressure with load.
- Final feedwater temperature: 288.3 °C at 630 MW (8-stage regen).

### TESPy 0.12 (Witte & Tuschy et al.)

TESPy, `tespy.readthedocs.io`, is the thermal-system simulator used
for the cycle. Its API was verified against the installed 0.12.0.post1
package (no bundled examples ship with the pip package; component
parameters were read from the installed source). Relevant behaviours
found by experiment, not assumed:

- A connection's `p`/`T`/`m` is a *specification*; `p0`/`T0`/`m0` are
  starting values only.
- Within one pressure-equality chain (turbine → splitter → heater,
  merge inlets/outlets, pump → heater → cycle closer → boiler) exactly
  one pressure may be specified, or the presolve rejects the problem
  as linearly dependent.
- The `Condenser` component already enforces a saturated hot outlet,
  so an extra `x = 0` specification on its outlet over-determines the
  problem.
- A component's `Q` is reported in W while `P` follows the power unit;
  all values are therefore read back with `val_SI`.

### PyPSA 1.x (Brown et al.) and pandapower 3.x

- PyPSA has no native piecewise marginal cost for one generator, so
  the curve is exported as one generator per segment (the standard
  representation), verified against installed PyPSA 1.2.4 with HiGHS.
- pandapower's `create_pwl_cost` takes areas `[p1, p2, slope]`, not
  `(p, cost)` points (read from the installed 3.5.6 source after an
  initial wrong guess failed loudly).
- pandapower's AC-OPF (PYPOWER MIPS, no PIPS installed) is fragile in
  this environment: it fails outright when the external grid carries
  `min/max_p_mw` limits, when generator reactive limits stay at the
  ±1e9 MVAr default, and when the external grid is allowed to dispatch
  negative (it then "sells" surplus power at its own high price). The
  demo network sets explicit tight Q limits, `min_p_mw = 0` on the grid,
  and otherwise uses the default solver settings. These are documented
  in `export_pandapower.py`, not hidden.

### Foundational methods

- Reheat regenerative Rankine cycle (textbook): one reheat plus
  feedwater heating raises the mean temperature of heat addition.
- Stodola's ellipse law (flow approximately proportional to pressure
  for a turbine stage group) for sliding-pressure operation.

## Innovation — the three required points

1. **Against existing tools.** TESPy simulates off-design thermal
   processes but produces no dispatch cost curve; PyPSA and pandapower
   need cost curves but cannot compute a thermal process; SAM, PVsyst
   and pvlib are unrelated to coal power. `heatrate` is the dedicated
   TESPy → PyPSA/pandapower bridge, a function neither side has.
2. **Against the author's own projects.** pvfade / pvhostcap /
   pvhost-prob / pvclip are all PV/storage; cpflow is grid voltage
   stability; dnrflow is distribution reconfiguration; kneebench,
   mutest and rag-checkup are not energy-system projects at all. No
   earlier project touches thermal power-plant thermodynamics — this
   is the only power-plant thermal topic.
3. **Whose real problem.** Power-system dispatch/planning researchers
   and students who today hand-fill quadratic cost curves or copy
   handbook typical values; flexibility-retrofit engineers who need
   the low-load heat-rate deterioration quantified (here: +11.2% heat
   rate from 100% to 30% load, supply coal +18.1%). The output plugs
   directly into PyPSA LOPF and pandapower OPF.

## Model and validation plan (what was actually done)

- Cycle: single reheat, 3-stage regen (HP heater fed by cold-reheat
  extraction + deaerator + LP heater), 24.2 MPa / 566 °C, condenser
  7 kPa, generator efficiency 0.99. Design point calibrated to 630 MW
  **net** (secant on main-steam flow, measured 5.26% auxiliary rate).
- Off-design: quasi-off-design re-solve per load point (design mode,
  Stodola pressures, quadratic turbine-efficiency law, measured
  boiler-efficiency and auxiliary-rate anchors). A native TESPy
  offdesign attempt was made and abandoned: the problem is 15
  equations short without turbine/heater/condenser characteristic
  curves, and adding them would hide the load laws the quasi method
  keeps explicit. The README states the method honestly.
- Validation: steam-side heat rate vs the paper's heat rate at 100 /
  75 / 50% (THA design) and at 630 / 300 MW (test measured); coal
  consumption vs the paper's 291.59 / 307.78 g/kWh at 630 MW. Results
  (see README): within +5.2% of the THA design values and within
  0.9% of the test measurements. The model reproduces the *as-tested*
  unit, which itself tests ~5% worse than its THA design figures.
- Known gaps, stated in the README: 3-stage regen reaches 254 °C
  feedwater vs the real 8-stage unit's 288 °C; main-steam flow
  519 kg/s vs 552 kg/s tested (and 499 kg/s THA design); HP
  cylinder efficiency is a smooth quadratic law while the real one is
  non-monotonic (valve sequencing); sliding pressure scales with load
  while the real unit throttles at high load; 105 MW is outside the
  sweep range (minimum 189 MW) and is not extrapolated.

## Earlier work this builds on

- pvfade (PV-storage ageing-aware sizing/dispatch) and the author's
  merged PRs in tespy / pvlib / PyBaMM / pandapower / PyPSA: the
  pattern is the same — a small, verified, single-purpose tool with
  tests and an honest validation section — applied here for the first
  time to a thermal power plant.

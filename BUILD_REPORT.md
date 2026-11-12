# heatrate — BUILD_REPORT

Built 2026-11-12. Spec: `BUILD_SPEC.md`. Environment:
`~/workspace/heatrate-venv/bin/python` (Python 3.12.3, TESPy 0.12.0.post1,
pandapower 3.5.6, PyPSA 1.2.4, HiGHS via highspy 1.16.0, CoolProp 8.0.0,
pytest 9.2.0, ruff 0.17.4 installed into the venv for linting).
Local build + verification only — no GitHub repository was created and
nothing was pushed (that step is the parent agent's).

## Measured results (all numbers from actual runs)

### Design point (calibrated to 630 MW net)

| quantity | value | reference |
|---|---|---|
| main-steam flow | 519.39 kg/s (1869.8 t/h) | test 552.4 kg/s (−6.0%), THA 499 kg/s (+4.1%) |
| net / gross / shaft power | 630.0 / 665.0 / 671.7 MW | — |
| pump power | 17.9 MW | — |
| steam-side heat rate | 7856.6 kJ/kWh | test 7840.32 (+0.21%), THA 7485 (+4.96%) |
| fuel heat rate | 8420.8 kJ/kWh | — |
| cycle efficiency | 45.82% | test "absolute" 45.92% (−0.10 pt) |
| boiler efficiency | 93.30% | assumption (paper: max 93.58% at 475 MW) |
| auxiliary rate | 5.26% | measured |
| coal, generation / supply | 290.60 / 306.73 g/kWh | 291.59 / 307.78 (−0.34% each) |
| feedwater temperature | 254.4 °C | test 288.3 °C (3-stage vs 8-stage regen) |
| extractions HP / IP / LP | 92.8 / 22.3 / 62.3 kg/s | all positive |
| energy-balance residual | 0.00 kW | Q_steam = shaft + condenser heat |

### Sweep (8 points, 30%–100%)

Heat rate (steam-side) 7856.6 → 8734.9 kJ/kWh (+11.2%); supply coal
306.7 → 362.3 g/kWh (+18.1%). Monotone in every column; the 50%→30%
rise (443 kJ/kWh) exceeds the 100%→75% rise (145 kJ/kWh) — low-load
deterioration accelerates, as in the paper. Full table in README.md.
Runtime: calibration ~0.5 s, full sweep ~2 s.

### Validation vs N630 (Zhang et al. 2025)

| load | model HR | measured | deviation | basis |
|---|---|---|---|---|
| 315 MW | 8292.3 | 7920.0 | +4.70% | THA design |
| 472 MW | 8001.7 | 7604.0 | +5.23% | THA design |
| 630 MW | 7856.6 | 7485.0 | +4.96% | THA design |
| 300 MW | 8336.8 | 8409.8 | −0.87% | test measured |
| 630 MW | 7856.6 | 7840.3 | +0.21% | test measured |

Largest deviation 5.23%. The 105 MW test point is outside the sweep
range (minimum 189 MW) and was not extrapolated.

### Fits (coal price 1000 CNY/t standard coal)

- Piecewise-linear, 4 segments (189/315/441/567/630 MW): max relative
  error 0.194% at sweep points; slopes pooled to monotone
  (272.84 / 272.84 / 273.84 / 279.56 CNY/MWh); continuous export
  curve max error 0.310%.
- Quadratic control fit: max relative error 0.254%;
  a=0.00330, b=270.66, c=11050.9 (F in kg/h, P in MW).
- Base block: 189 MW at 329.1 CNY/MWh average cost.

### Dispatch demos (verified by tests)

- PyPSA LOPF (HiGHS): 400 MW load → unit 400.0 MW, peaker 0.0 MW;
  700 MW load → unit 630.0 MW, peaker 70.0 MW; 150 MW load →
  infeasible (below the 189 MW minimum stable load), reported as an
  error, not a dispatch.
- pandapower OPF (pwl and poly): 200 MW → unit 200.0, grid 0.0;
  400 MW → unit 400.0, grid 0.0; 700 MW → unit 630.0, grid 70.0;
  all converged.

### Tests

31 passed in ~24 s (`pytest -q`): design point, sweep monotonicity,
fit accuracy/monotonicity, both exports, validation, CLI end-to-end.
`ruff check` and `ruff format --check` pass; `python -m compileall`
passes. Quickstart runs in ~19 s. Full suite + quickstart < 1 min
(target < 10 min).

## Problems encountered and fixed

1. **Negative IP extraction in the first topology.** With the HP
   heater fed by 80 bar HPT1 extraction and a 180→292 °C feedwater
   rise, the extraction was 28.7% of main steam and its 295 °C drain
   over-supplied the deaerator, so the solver returned a −1.5 kg/s IP
   extraction. Fixed by feeding the HP heater from cold reheat
   (45 bar, feedwater outlet 253 °C, textbook TTD = 3 K) — all
   extractions positive thereafter (92.8 / 22.3 / 62.3 kg/s).
2. **TESPy linear-dependence rejections.** Within one
   pressure-equality chain exactly one pressure may be specified.
   Fixed by specifying one pressure per chain and letting the rest
   follow through component pressure ratios (boiler `pr`, reheater
   `pr`, heater `pr = 1`).
3. **Condenser double specification.** The `Condenser` component
   already enforces a saturated hot outlet; an extra `x = 0` on its
   outlet over-determines the problem. Removed.
4. **Boiler-efficiency/aux-rate law returned the end anchor at every
   load.** `np.interp` requires ascending x; the anchor lists were
   descending. Fixed by sorting anchors before interpolating
   (caught because the design point showed η_boiler = 89.61% at
   full load).
5. **TESPy `Q` vs `P` units.** In TESPy 0.12 a component's `Q` is
   reported in W while `P` follows the power unit. All values are
   read back with `val_SI` and converted explicitly.
6. **Native TESPy offdesign is 15 equations short.** Attempted once
   (design save + `mode='offdesign'` with `eta_s` held at design
   values): the problem needs turbine/heater/condenser
   characteristics that would hide the load laws. Shipped the
   quasi-off-design re-solve instead, labelled honestly everywhere.
7. **pandapower `create_pwl_cost` point format.** It takes areas
   `[p1, p2, slope]`, not `(p, cost)` points (found in the installed
   3.5.6 source after the first call failed).
8. **pandapower AC-OPF (PYPOWER MIPS, no PIPS) is fragile.**
   Three independent triggers found by bisection: (a) `min/max_p_mw`
   on the external grid breaks convergence; (b) the ±1e9 MVAr default
   reactive limits break convergence — explicit tight Q limits are
   set; (c) a free external grid is dispatched negative (the solver
   "sells" surplus at its own high price) — `min_p_mw = 0` is set.
   With all three handled, pwl and poly converge at 200/400/700 MW.
   Also fixed a PyPSA `FutureWarning` by passing
   `include_objective_constant=False` explicitly.

## Open issues / follow-ups (not blockers)

- Native TESPy offdesign with proper characteristics (turbine cone /
  `eta_s_char`, heater kA) is a possible later enhancement; it would
  need its own validation round.
- The 105 MW deep-peak point (16.67% load) is outside the sweep range;
  extending the sweep below 30% would need a low-load deaerator /
  heater setpoint review (extraction pressures fall below 1 bar).
- CI (GitHub Actions) has not been run — no repository exists yet.
  The workflow installs `.[test]` plus ruff; TESPy/pandapower/PyPSA
  are heavy installs, so the first CI run may take several minutes.
- `ruff` was installed into the project venv for linting (not part of
  the package dependencies); CI installs it separately, as in the
  workflow file.

# heatrate

[![tests: 31 passed](https://img.shields.io/badge/tests-31%20passed-brightgreen.svg)](tests/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

**English** | [简体中文](#heatrate-中文)

**A dispatch study needs a fuel-cost curve for its coal unit. `heatrate` computes it from a thermodynamic model instead of copying a handbook value — a TESPy reheat regenerative cycle, swept from 30% to 100% load, fitted as a piecewise-linear cost curve, and exported straight into PyPSA and pandapower.**

## Results at a glance

Design point (calibrated to 630 MW net): main steam 519.4 kg/s
(1869.8 t/h), steam-side heat rate **7856.6 kJ/kWh**, cycle efficiency
45.82%, standard-coal consumption 290.6 g/kWh (generation) /
306.7 g/kWh (supply). Energy balance closes to 0.00 kW.

Load sweep (quasi-off-design, 8 points):

| load | P (MW) | m (kg/s) | p_ms (bar) | fwT (°C) | HR_steam | HR_fuel | η_cycle | η_boiler | coal_g | coal_s |
|---|---|---|---|---|---|---|---|---|---|---|
| 30% | 189.0 | 157.6 | 72.6 | 190.3 | 8734.9 | 9537.3 | 0.4121 | 0.9159 | 329.1 | 362.3 |
| 40% | 252.0 | 203.7 | 96.8 | 204.1 | 8478.9 | 9133.8 | 0.4246 | 0.9283 | 315.2 | 338.3 |
| 50% | 315.0 | 249.6 | 121.0 | 215.4 | 8292.3 | 8912.5 | 0.4341 | 0.9304 | 307.6 | 323.9 |
| 60% | 378.0 | 299.8 | 145.2 | 225.1 | 8151.1 | 8740.8 | 0.4417 | 0.9325 | 301.6 | 317.1 |
| 70% | 441.0 | 351.0 | 169.4 | 233.6 | 8042.9 | 8605.2 | 0.4476 | 0.9347 | 297.0 | 311.7 |
| 80% | 504.0 | 404.4 | 193.6 | 241.2 | 7960.5 | 8511.4 | 0.4522 | 0.9353 | 293.7 | 308.4 |
| 90% | 567.0 | 460.7 | 217.8 | 248.1 | 7899.4 | 8456.3 | 0.4557 | 0.9341 | 291.8 | 307.2 |
| 100% | 630.0 | 519.4 | 242.0 | 254.4 | 7856.6 | 8420.8 | 0.4582 | 0.9330 | 290.6 | 306.7 |

Heat rates in kJ/kWh; coal consumption in g/kWh of standard coal
(LHV 29.27 MJ/kg). `HR_steam` is the steam-side heat rate (boiler +
reheater heat per kWh generated) — the paper's definition;
`HR_fuel` divides by the boiler efficiency.

```console
$ heatrate sweep
$ heatrate validate
$ heatrate export --format pypsa --load 400
$ heatrate export --format pandapower --cost pwl --load 400
```

Three findings worth a dispatch modeller's attention:

1. **The model reproduces the as-tested unit, not the as-designed
   one.** Against the test-measured heat rates the deviation is
   +0.21% at 630 MW and −0.87% at 300 MW; against the THA design
   values it is +4.7% to +5.2% — because the real unit itself tests
   ~5% worse than its THA figures (valve throttling, HP cylinder at
   84.12% instead of the design 87.34%).
2. **Low-load deterioration accelerates.** From 100% to 75% load the
   heat rate rises ~145 kJ/kWh; from 50% to 30% it rises ~443 kJ/kWh.
   Supply coal consumption rises 18.1% from 100% to 30% load
   (306.7 → 362.3 g/kWh) — the number that decides whether deep peak
   shaving pays.
3. **The fuel curve is nearly linear, with a fixed-cost core.** The
   4-segment fit (breakpoints 189 / 315 / 441 / 567 / 630 MW) has a
   maximum relative error of 0.19%; marginal costs are 272.8 / 272.8 /
   273.8 / 279.6 CNY/MWh, and the minimum-load block (189 MW) carries
   the no-load fuel as a 329.1 CNY/MWh average cost. The quadratic
   control fit errs by 0.25%.

## How it works

**Cycle** (`cycle.py`): a TESPy model of a supercritical unit —
24.2 MPa / 566 °C main steam, single reheat to 566 °C, three-stage
regenerative feedwater heating (HP heater fed by cold-reheat
extraction, deaerator, LP heater), condenser at 7 kPa, generator
efficiency 0.99. The boiler and reheater are heat-addition pipes: only
the steam side is simulated, so the boiler heat input is the
steam-side enthalpy rise and the fuel heat follows from the boiler
efficiency. The design point is calibrated to 630 MW **net** by a
secant iteration on the main-steam flow (519.4 kg/s), using the
measured 630 MW auxiliary rate of 5.26%.

**Off-design** (`offdesign.py`): a *quasi-off-design* re-solve — every
load point is solved again in TESPy design mode with load-dependent
setpoints, so every law stays explicit and auditable:

- sliding pressure (Stodola): all turbine-stage pressures scale with
  the load fraction; condenser pressure fixed at 7 kPa; steam
  temperatures fixed at 566 °C;
- turbine isentropic efficiency: quadratic drop
  `η_s(f) = η_s,design − a·(1−f)²` with a = 0.08 (HP), 0.03 (IP),
  0.07 (LP), chosen from the cylinder-efficiency drops measured in
  Zhang et al. (2025);
- boiler efficiency and auxiliary rate: piecewise-linear interpolation
  through the values measured in Zhang et al. (2025) — 93.58% boiler
  efficiency at 475 MW, 92.79% at 240 MW, 89.61% at 105 MW;
  5.26% / 4.63% / 5.08% / 12.22% auxiliary rate at 630 / 475 / 300 /
  105 MW. The 630 MW boiler efficiency is not stated in the paper, so
  the design point is taken as 93.3% and labelled as an assumption.

A native TESPy `mode='offdesign'` attempt was made and abandoned: the
problem is 15 equations short without turbine/heater/condenser
characteristic curves, and adding them would hide the load laws the
re-solve keeps explicit. The method is therefore quasi-off-design, and
is labelled as such everywhere — it is not claimed to be native
offdesign.

**Cost curve** (`fit.py`): fuel rate `F(P) = coal_gen(P) · P` in kg/h of
standard coal; cost at 1000 CNY/t (the price used in the paper's
deep-peak-regulation benefit analysis). Piecewise-linear least-squares
fit per segment, with isotonic pooling of the slopes so the marginal
cost is non-decreasing (a convexity requirement for merit-order
dispatch); the exported total-cost curve integrates those slopes from
the minimum-load point (max error 0.31% against the simulated fuel
rates). A quadratic fit is provided as a control.

**Exports**: PyPSA gets one generator per segment plus a must-run
189 MW base block (`export_pypsa.py`); pandapower gets a
piecewise-linear cost (`create_pwl_cost`, areas `[p1, p2, slope]`) and
a quadratic cost (`create_poly_cost`) (`export_pandapower.py`). Costs
are in CNY/MWh.

## Usage

```console
$ heatrate sweep [--fractions 1.0,0.9,0.8,0.7,0.6,0.5,0.4,0.3] [--json out.json]
$ heatrate validate
$ heatrate export --format pypsa --load 400
$ heatrate export --format pandapower --cost pwl|poly --load 400
```

Python API:

```python
from heatrate import calibrate_design
from heatrate.offdesign import sweep
from heatrate.fit import fit_piecewise, fit_quadratic, fuel_rates
from heatrate.export_pypsa import run_lopf
from heatrate.export_pandapower import run_opf

design = calibrate_design()          # 630 MW net, heat rate 7856.6 kJ/kWh
rows = sweep(design=design)          # 8 load points, 30%-100%
p = [r.net_power_kw / 1000 for r in rows]
f = fuel_rates(p, [r.coal_gen_g_per_kwh for r in rows])
pw = fit_piecewise(p, f)             # max rel. error 0.19%
quad = fit_quadratic(p, f)           # max rel. error 0.25%

dispatch = run_lopf(pw, load_mw=400.0)   # heat-rate unit: 400.0 MW
gen, ext, ok = run_opf(pw, quad, load_mw=400.0, cost="pwl")  # 400.0 MW, True
```

Dispatch demo results (all verified by tests):

| demo | load | heat-rate unit | other source |
|---|---|---|---|
| PyPSA LOPF | 400 MW | 400.0 MW | peaker 0.0 MW |
| PyPSA LOPF | 700 MW | 630.0 MW (max) | peaker 70.0 MW |
| PyPSA LOPF | 150 MW | **infeasible** — below the 189 MW minimum stable load |
| pandapower OPF (pwl / poly) | 200 MW | 200.0 MW | ext. grid 0.0 MW |
| pandapower OPF (pwl / poly) | 400 MW | 400.0 MW | ext. grid 0.0 MW |
| pandapower OPF (pwl / poly) | 700 MW | 630.0 MW (max) | ext. grid 70.0 MW |

Note on the PyPSA 400 MW dispatch: segments 1 and 2 share the pooled
marginal cost (272.8 CNY/MWh), so the split between them (85 / 126 MW)
is arbitrary; the more expensive segments stay empty, as merit order
requires.

## Validation against the N630 measurements

Zhang et al. (2025), DOI 10.3389/fenrg.2025.1611001. The paper's heat
rate is the steam-side heat rate, so the model's steam-side heat rate
is the like-for-like comparator. The 105 MW test point is outside the
sweep range (minimum 189 MW) and is **not** extrapolated.

| load (MW) | model HR | measured HR | deviation | basis |
|---|---|---|---|---|
| 315 | 8292.3 | 7920.0 | +4.70% | THA design |
| 472 | 8001.7 | 7604.0 | +5.23% | THA design |
| 630 | 7856.6 | 7485.0 | +4.96% | THA design |
| 300 | 8336.8 | 8409.8 | −0.87% | test measured |
| 630 | 7856.6 | 7840.3 | +0.21% | test measured |

Standard-coal consumption at 630 MW: model 290.6 g/kWh (generation)
vs 291.59 measured (−0.34%); 306.7 vs 307.78 g/kWh (supply, −0.34%).
Main-steam flow at design: model 519.4 kg/s vs 552.4 kg/s tested
(−6.0%) and 499 kg/s THA design (+4.1%).

## Honesty notes

- **Quasi-off-design, not native offdesign.** See "How it works"
  above; a native-mode attempt was made and is documented in
  `BUILD_REPORT.md`.
- **Three-stage vs eight-stage regeneration.** The real unit has 8
  feedwater heaters; this model has 3. Feedwater reaches 254.4 °C
  instead of the real 288.3 °C, and the main-steam flow needed for
  630 MW is 6.0% lower than tested. The heat-rate agreement (+0.21%
  vs the test value) is therefore partly a cancellation of errors
  (fewer heaters vs slightly optimistic turbine efficiencies), and is
  reported as such — no parameter was tuned to match the heat rate.
- **Smooth efficiency laws vs valve sequencing.** The real HP cylinder
  efficiency is non-monotonic with load (84.12% → 77.15% → 80.24% →
  69.15%) because regulating valves open and close; the model uses a
  smooth quadratic law and cannot reproduce that.
- **Sliding pressure is approximate.** The model scales all stage
  pressures with the load fraction; the real unit's pressure falls
  less steeply (23.98 MPa at 630 MW, 22.48 at 475 MW, 15.77 at
  300 MW) because of throttle-valve operation at high load.
- **Boiler efficiency at 630 MW is assumed (93.3%).** The paper states
  the maximum (93.58% at 475 MW) but not the 630 MW value; the anchor
  is labelled as an assumption in `offdesign.py`.
- **The pandapower OPF demo needs three solver workarounds**
  (verified in this environment, pandapower 3.5.6, PYPOWER MIPS, no
  PIPS): explicit tight reactive-power limits (the ±1e9 MVAr defaults
  make MIPS fail), `min_p_mw = 0` on the external grid (otherwise the
  solver "sells" surplus power back to the grid at its own high
  price), and no `min/max_p_mw` limits on the external grid (they
  break convergence). All three are documented in
  `export_pandapower.py`.
- **TESPy unit quirk:** a component's `Q` is reported in W while `P`
  follows the power unit in TESPy 0.12; all values are read back with
  `val_SI` (see `cycle.py`).

## Tests

31 tests, all passing in ~24 s: design-point calibration and energy
balance, sweep monotonicity and low-load acceleration, fit accuracy
and monotone slopes, PyPSA LOPF and pandapower OPF dispatch,
validation against the N630 data, and CLI end-to-end runs.

```console
$ pip install -e ".[test]"
$ pytest -q
$ python examples/quickstart.py
```

## References

- Zhang et al., "Thermal economy analysis on deep peak regulation
  operation of supercritical 630 MW coal-fired unit", *Front. Energy
  Res.* 13:1611001 (2025), DOI 10.3389/fenrg.2025.1611001 — the
  validation set (THA design values, wide-load test data, boiler
  efficiency, auxiliary rate, coal-consumption formula, coal price
  1000 CNY/t).
- TESPy 0.12 (Witte & Tuschy et al.), `tespy.readthedocs.io` — thermal
  system simulation.
- PyPSA 1.x (Brown et al.), `pypsa.readthedocs.io` — LOPF, HiGHS
  solver.
- pandapower 3.x — OPF (`runopp`, PYPOWER MIPS).
- Rankine reheat regenerative cycle; Stodola's ellipse law for
  sliding-pressure operation.

---

# heatrate （中文）

**English** | **简体中文**

**做调度研究需要一台燃煤机组的燃料成本曲线。`heatrate` 不从手册抄典型值，而是从热力模型算出来——TESPy 一次中间再热回热循环，30%–100% 负荷扫掠，拟合成分段线性成本曲线，直接导出给 PyPSA 和 pandapower 用。**

## 一眼结果

设计点（标定到 630 MW 净出力）：主蒸汽 519.4 kg/s（1869.8 t/h），汽机侧热耗率 **7856.6 kJ/kWh**，循环效率 45.82%，发电标煤耗 290.6 g/kWh、供电标煤耗 306.7 g/kWh。能量平衡残差 0.00 kW。

负荷扫掠（准 off-design，8 个点）：

| 负荷 | 功率 (MW) | 主汽流量 (kg/s) | 主汽压力 (bar) | 给水温度 (°C) | 汽机热耗 | 燃料热耗 | 循环效率 | 锅炉效率 | 发电煤耗 | 供电煤耗 |
|---|---|---|---|---|---|---|---|---|---|---|
| 30% | 189.0 | 157.6 | 72.6 | 190.3 | 8734.9 | 9537.3 | 0.4121 | 0.9159 | 329.1 | 362.3 |
| 40% | 252.0 | 203.7 | 96.8 | 204.1 | 8478.9 | 9133.8 | 0.4246 | 0.9283 | 315.2 | 338.3 |
| 50% | 315.0 | 249.6 | 121.0 | 215.4 | 8292.3 | 8912.5 | 0.4341 | 0.9304 | 307.6 | 323.9 |
| 60% | 378.0 | 299.8 | 145.2 | 225.1 | 8151.1 | 8740.8 | 0.4417 | 0.9325 | 301.6 | 317.1 |
| 70% | 441.0 | 351.0 | 169.4 | 233.6 | 8042.9 | 8605.2 | 0.4476 | 0.9347 | 297.0 | 311.7 |
| 80% | 504.0 | 404.4 | 193.6 | 241.2 | 7960.5 | 8511.4 | 0.4522 | 0.9353 | 293.7 | 308.4 |
| 90% | 567.0 | 460.7 | 217.8 | 248.1 | 7899.4 | 8456.3 | 0.4557 | 0.9341 | 291.8 | 307.2 |
| 100% | 630.0 | 519.4 | 242.0 | 254.4 | 7856.6 | 8420.8 | 0.4582 | 0.9330 | 290.6 | 306.7 |

热耗单位 kJ/kWh；煤耗为标煤 g/kWh（低位热值 29.27 MJ/kg）。`HR_steam` 是汽机侧热耗率（锅炉+再热器吸热/发电量），即论文的定义；`HR_fuel` 再除以锅炉效率。

```console
$ heatrate sweep
$ heatrate validate
$ heatrate export --format pypsa --load 400
$ heatrate export --format pandapower --cost pwl --load 400
```

三点值得注意：

1. **模型复现的是实测机组，不是设计值。**与实测热耗率对照，630 MW 偏差 +0.21%、300 MW 偏差 −0.87%；与 THA 设计值对照偏差 +4.7%–+5.2%——因为真实机组实测本身就比 THA 设计值差约 5%（调门节流、高压缸效率 84.12% 而非设计 87.34%）。
2. **低负荷恶化在加速。**100%→75% 负荷热耗上升约 145 kJ/kWh；50%→30% 上升约 443 kJ/kWh。供电煤耗从 100% 到 30% 负荷上升 18.1%（306.7 → 362.3 g/kWh）——这个数决定深度调峰划不划算。
3. **燃料曲线接近线性，核心是一块固定成本。**4 段拟合（断点 189 / 315 / 441 / 567 / 630 MW）最大相对误差 0.19%；边际成本 272.8 / 272.8 / 273.8 / 279.6 元/MWh；最低负荷段（189 MW）以 329.1 元/MWh 的平均成本承担空载燃料。二次拟合对照误差 0.25%。

## 做法

**循环**（`cycle.py`）：TESPy 超临界机组模型——主蒸汽 24.2 MPa / 566 °C、一次再热到 566 °C、三级回热（高加由冷再热抽汽供汽、除氧器、低加）、凝汽器 7 kPa、发电机效率 0.99。锅炉与再热器按吸热管道建模：只仿真蒸汽侧，锅炉吸热即蒸汽侧焓升，燃料热量由锅炉效率折算。设计点用割线法迭代主蒸汽流量标定到 630 MW **净出力**（519.4 kg/s），厂用电率取实测 630 MW 值 5.26%。

**变工况**（`offdesign.py`）：*准 off-design* 重解——每个负荷点用 TESPy 设计模式按负荷相关定值重新求解，每条规律都显式写在代码里、可审计：

- 滑压运行（Stodola 近似）：各级汽轮机压力随负荷分数成比例变化；凝汽器压力固定 7 kPa；蒸汽温度固定 566 °C；
- 汽轮机等熵效率二次下降 `η_s(f) = η_s,设计 − a·(1−f)²`，a 取 0.08（高压缸）、0.03（中压缸）、0.07（低压缸），依据 Zhang 等（2025）实测的缸效率下降幅度；
- 锅炉效率与厂用电率：按 Zhang 等（2025）实测值分段线性插值——锅炉效率 475 MW 时 93.58%、240 MW 时 92.79%、105 MW 时 89.61%；厂用电率 630 / 475 / 300 / 105 MW 时分别为 5.26% / 4.63% / 5.08% / 12.22%。论文未给出 630 MW 锅炉效率，设计点取 93.3%，在代码里标注为假设。

原生 TESPy `mode='offdesign'` 尝试过但放弃：不补汽轮机/加热器/凝汽器的特性曲线，问题欠定 15 个方程；而补上特性曲线会把变工况规律藏进默认特性，失去显式可审计性。所以本项目的方法是准 off-design，各处都如实标注，绝不谎称原生 off-design。

**成本曲线**（`fit.py`）：燃料消耗率 `F(P) = 煤耗(P) · P`（标煤 kg/h）；煤价按 1000 元/吨（论文深度调峰效益分析所用价格）。每段最小二乘直线拟合，斜率经 isotonic pooling 保证边际成本单调不减（merit-order 调度对凸性的要求）；导出用的总成本曲线由各段斜率从最低负荷点积分得到（与仿真燃料消耗的最大误差 0.31%）。二次拟合作对照。

**导出**：PyPSA 为每段一台发电机加一台 189 MW 必开基础块（`export_pypsa.py`）；pandapower 提供分段线性成本（`create_pwl_cost`，`[p1, p2, 斜率]` 区间形式）与二次成本（`create_poly_cost`）（`export_pandapower.py`）。成本单位均为元/MWh。

## 用法

```console
$ heatrate sweep [--fractions 1.0,0.9,0.8,0.7,0.6,0.5,0.4,0.3] [--json out.json]
$ heatrate validate
$ heatrate export --format pypsa --load 400
$ heatrate export --format pandapower --cost pwl|poly --load 400
```

Python 调用：

```python
from heatrate import calibrate_design
from heatrate.offdesign import sweep
from heatrate.fit import fit_piecewise, fit_quadratic, fuel_rates
from heatrate.export_pypsa import run_lopf
from heatrate.export_pandapower import run_opf

design = calibrate_design()          # 630 MW 净出力，热耗 7856.6 kJ/kWh
rows = sweep(design=design)          # 8 个负荷点，30%–100%
p = [r.net_power_kw / 1000 for r in rows]
f = fuel_rates(p, [r.coal_gen_g_per_kwh for r in rows])
pw = fit_piecewise(p, f)             # 最大相对误差 0.19%
quad = fit_quadratic(p, f)           # 最大相对误差 0.25%

dispatch = run_lopf(pw, load_mw=400.0)   # 机组出力 400.0 MW
gen, ext, ok = run_opf(pw, quad, load_mw=400.0, cost="pwl")  # 400.0 MW, True
```

调度演示结果（均有测试覆盖）：

| 演示 | 负荷 | 机组出力 | 另一电源 |
|---|---|---|---|
| PyPSA LOPF | 400 MW | 400.0 MW | 调峰机组 0.0 MW |
| PyPSA LOPF | 700 MW | 630.0 MW（满发） | 调峰机组 70.0 MW |
| PyPSA LOPF | 150 MW | **不可行**——低于 189 MW 最低稳燃负荷 |
| pandapower OPF（pwl / poly） | 200 MW | 200.0 MW | 外网 0.0 MW |
| pandapower OPF（pwl / poly） | 400 MW | 400.0 MW | 外网 0.0 MW |
| pandapower OPF（pwl / poly） | 700 MW | 630.0 MW（满发） | 外网 70.0 MW |

说明：PyPSA 400 MW 算例中第 1、2 段边际成本 pooled 后相同（272.8 元/MWh），两者之间的分配（85 / 126 MW）是任意的；更贵的两段保持零出力，符合 merit order。

## 与 N630 实测对照

Zhang 等（2025），DOI 10.3389/fenrg.2025.1611001。论文的热耗率是汽机侧热耗率，模型用汽机侧热耗率作同口径对照。105 MW 实测点在扫掠范围之外（最低 189 MW），**不做外推**。

| 负荷 (MW) | 模型热耗 | 实测热耗 | 偏差 | 依据 |
|---|---|---|---|---|
| 315 | 8292.3 | 7920.0 | +4.70% | THA 设计值 |
| 472 | 8001.7 | 7604.0 | +5.23% | THA 设计值 |
| 630 | 7856.6 | 7485.0 | +4.96% | THA 设计值 |
| 300 | 8336.8 | 8409.8 | −0.87% | 实测 |
| 630 | 7856.6 | 7840.3 | +0.21% | 实测 |

630 MW 标煤耗：模型发电 290.6 g/kWh，对实测 291.59（−0.34%）；供电 306.7 对 307.78 g/kWh（−0.34%）。设计点主蒸汽流量：模型 519.4 kg/s，对实测 552.4 kg/s（−6.0%）、THA 设计 499 kg/s（+4.1%）。

## 诚实说明

- **准 off-design，不是原生 off-design。**见"做法"一节；原生模式的尝试过程记在 `BUILD_REPORT.md`。
- **三级回热 vs 八级回热。**真实机组有 8 级回热，本模型只有 3 级。给水温度只能到 254.4 °C（实测 288.3 °C），630 MW 所需主蒸汽流量比实测少 6.0%。热耗率与实测吻合（+0.21%）部分是误差抵消（回热级数少 vs 汽轮机效率略乐观），如实说明——没有任何参数是为贴近热耗率而调过的。
- **效率规律平滑 vs 调门动作。**真实高压缸效率随负荷非单调变化（84.12% → 77.15% → 80.24% → 69.15%），源于调门启闭；模型用平滑二次规律，复现不了这一点。
- **滑压是近似。**模型令各级压力随负荷分数成比例变化；真实机组高负荷段靠调门节流，压力下降更平缓（630 MW 时 23.98 MPa、475 MW 时 22.48 MPa、300 MW 时 15.77 MPa）。
- **630 MW 锅炉效率是假设值（93.3%）。**论文只给出峰值（475 MW 时 93.58%），未给出 630 MW 值；该锚点在 `offdesign.py` 里标注为假设。
- **pandapower OPF 演示需要三处求解器变通**（本环境实测，pandapower 3.5.6、PYPOWER MIPS、无 PIPS）：无功限值必须显式收紧（默认 ±1e9 MVAr 会使 MIPS 直接失败）、外网 `min_p_mw = 0`（否则求解器会以自身高价倒卖富余电力）、外网不设 `min/max_p_mw`（设了就不收敛）。三处都写在 `export_pandapower.py` 的注释里。
- **TESPy 单位坑：**TESPy 0.12 里部件的 `Q` 以 W 报告而 `P` 跟随功率单位；所有数值一律用 `val_SI` 读取（见 `cycle.py`）。

## 测试

31 个测试，约 24 秒全部通过：设计点标定与能量平衡、扫掠单调性与低负荷加速恶化、拟合精度与斜率单调、PyPSA LOPF 与 pandapower OPF 调度、N630 实测对照、CLI 端到端。

```console
$ pip install -e ".[test]"
$ pytest -q
$ python examples/quickstart.py
```

## 参考文献

- Zhang 等，"Thermal economy analysis on deep peak regulation operation of supercritical 630 MW coal-fired unit"，《Front. Energy Res.》13:1611001（2025），DOI 10.3389/fenrg.2025.1611001——验证数据集（THA 设计值、宽负荷试验数据、锅炉效率、厂用电率、煤耗公式、煤价 1000 元/吨）。
- TESPy 0.12（Witte & Tuschy 等），`tespy.readthedocs.io`——热力系统仿真。
- PyPSA 1.x（Brown 等），`pypsa.readthedocs.io`——LOPF，HiGHS 求解器。
- pandapower 3.x——OPF（`runopp`，PYPOWER MIPS）。
- 朗肯再热回热循环；滑压运行 Stodola 椭圆定律。

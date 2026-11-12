"""TESPy model of a 630 MW supercritical reheat regenerative coal unit.

Topology: single reheat, three-stage regenerative feedwater heating
(HP heater + deaerator + LP heater), sliding-pressure operation.

The boiler and the reheater are modelled as heat-addition pipes: only the
steam side is simulated in TESPy, so the boiler heat input is the
steam-side enthalpy rise and the fuel heat follows from the boiler
efficiency (an off-design law, see :mod:`heatrate.offdesign`). The HP
heater is fed by cold-reheat extraction (a standard arrangement); its
drain cascades to the deaerator and the LP heater drain to the condenser.

Off-design is handled by :mod:`heatrate.offdesign` as a *quasi-off-design*
re-solve: every load point is solved again in TESPy design mode with the
load-dependent setpoints (Stodola pressures, turbine-efficiency law,
heater terminal temperatures). This is stated openly in the README; the
model does not claim native TESPy offdesign mode.

Units: TESPy is run with bar / degC / kg/s / kJ/kg / kW display units, but
every value read back here uses ``val_SI`` and is converted explicitly, so
the results do not depend on TESPy's display-unit choices (note: in TESPy
0.12 a component's ``Q`` is reported in W while ``P`` follows the power
unit, which is why ``val_SI`` is used throughout).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from CoolProp.CoolProp import PropsSI
from tespy.components import (
    Condenser,
    CycleCloser,
    HeatExchanger,
    Merge,
    Pipe,
    Pump,
    Sink,
    Source,
    Splitter,
    Turbine,
    Valve,
)
from tespy.connections import Connection
from tespy.networks import Network

from .data import PIPING_EFFICIENCY
from .offdesign import aux_rate, boiler_efficiency, turbine_eta_s

#: Design-point constants (N630-24.2/566/566).
P_MAIN_STEAM_BAR = 242.0
T_MAIN_STEAM_C = 566.0
T_REHEAT_C = 566.0
P_HP1_OUT_BAR = 80.0
P_REHEAT_BAR = 45.0
P_REHEAT_OUT_BAR = 44.0
P_DEAERATOR_BAR = 9.0
P_LP_EXT_BAR = 2.5
P_CONDENSER_BAR = 0.07
P_FEED_PUMP_OUT_BAR = 250.0
#: Generator efficiency (fixed).
GENERATOR_EFFICIENCY = 0.99
#: Rated net power, kW.
RATED_NET_POWER_KW = 630_000.0
#: Heater terminal temperature difference, K (cold outlet vs saturation
#: temperature at the extraction pressure).
HEATER_TTD_K = 3.0
#: Cooling-water temperatures, degC.
CW_IN_C = 20.0
CW_OUT_C = 30.0

#: Design-point isentropic efficiencies.
ETA_S_DESIGN = {"hp": 0.89, "ip": 0.90, "lp1": 0.89, "lp2": 0.86}
ETA_S_PUMP = {"cond": 0.78, "feed": 0.80}


def saturation_temp_c(p_bar: float) -> float:
    """Saturation temperature in degC at ``p_bar`` (CoolProp, water)."""
    return PropsSI("T", "P", p_bar * 1e5, "Q", 0, "Water") - 273.15


@dataclass
class DesignResult:
    """One solved load point (all powers in kW, heat rates in kJ/kWh)."""

    load_fraction: float
    main_steam_flow_kg_per_s: float
    net_power_kw: float
    gross_power_kw: float
    shaft_power_kw: float
    pump_power_kw: float
    boiler_heat_kw: float
    reheat_heat_kw: float
    steam_heat_kw: float
    condenser_heat_kw: float
    heat_rate_steam: float
    heat_rate_fuel: float
    cycle_efficiency: float
    boiler_efficiency: float
    aux_rate: float
    coal_gen_g_per_kwh: float
    coal_supply_g_per_kwh: float
    feedwater_temp_c: float
    main_steam_pressure_bar: float
    reheat_pressure_bar: float
    condenser_pressure_bar: float
    extraction_hp_kg_per_s: float
    extraction_ip_kg_per_s: float
    extraction_lp_kg_per_s: float
    energy_balance_residual_kw: float
    converged: bool = True
    states: dict = field(default_factory=dict)

    @property
    def power_mw(self) -> float:
        return self.net_power_kw / 1000.0


def _conn(src, out, tgt, inn, label, **kwargs):
    return Connection(src, out, tgt, inn, label=label, **kwargs)


def build_network(load_fraction: float, m_main: float, start: dict | None = None):
    """Build the TESPy network for one load point.

    Parameters
    ----------
    load_fraction:
        Fraction of rated load (1.0 = design point). Pressures scale with
        the load fraction (Stodola: flow proportional to pressure);
        the condenser pressure stays fixed.
    m_main:
        Main-steam mass flow, kg/s.
    start:
        Optional dict ``{connection label: (m, p_bar, T_C, h_kJ_per_kg)}``
        of starting values, e.g. the previous (higher-load) solution.
        Improves convergence at low load.
    """
    f = load_fraction
    eta = {k: turbine_eta_s(k, f) for k in ("hp", "ip", "lp1", "lp2")}
    p_ms = P_MAIN_STEAM_BAR * f
    p_rh = P_REHEAT_BAR * f
    p_rh_out = P_REHEAT_OUT_BAR * f
    p_deaer = P_DEAERATOR_BAR * f
    p_lp = P_LP_EXT_BAR * f
    t_hp_fw = saturation_temp_c(p_rh) - HEATER_TTD_K
    t_lp_fw = saturation_temp_c(p_lp) - HEATER_TTD_K

    nw = Network(iterinfo=False)
    nw.units.set_defaults(
        pressure="bar",
        temperature="degC",
        mass_flow="kg/s",
        enthalpy="kJ/kg",
        power="kW",
    )

    boiler = Pipe("boiler", pr=P_MAIN_STEAM_BAR / P_FEED_PUMP_OUT_BAR)
    hpt1 = Turbine("hpt1", eta_s=eta["hp"])
    hpt2 = Turbine("hpt2", eta_s=eta["hp"])
    sp_rh = Splitter("sp_rh", num_out=2)
    rh = Pipe("reheater", pr=P_REHEAT_OUT_BAR / P_REHEAT_BAR)
    ipt = Turbine("ipt", eta_s=eta["ip"])
    sp_ip = Splitter("sp_ip", num_out=2)
    lpt1 = Turbine("lpt1", eta_s=eta["lp1"])
    sp_lp = Splitter("sp_lp", num_out=2)
    lpt2 = Turbine("lpt2", eta_s=eta["lp2"])
    cond = Condenser("condenser", pr1=0.999, pr2=0.999)
    cpump = Pump("cond_pump", eta_s=ETA_S_PUMP["cond"])
    lphtr = HeatExchanger("lp_heater", pr1=1.0, pr2=1.0)
    deaer = Merge("deaerator", num_in=3)
    fpump = Pump("feed_pump", eta_s=ETA_S_PUMP["feed"])
    hphtr = HeatExchanger("hp_heater", pr1=1.0, pr2=1.0)
    v_hp = Valve("hp_drain_valve")
    v_lp = Valve("lp_drain_valve")
    m_cond = Merge("cond_mix", num_in=2)
    cc = CycleCloser("cycle_closer")
    cw_src = Source("cw_source")
    cw_sink = Sink("cw_sink")

    def sv(label, m0, p0, t0):
        """Starting values: from the previous solution if available."""
        if start and label in start:
            m, p, t, _h = start[label]
            return {"m0": m, "p0": p, "T0": t}
        return {"m0": m0, "p0": p0, "T0": t0}

    conns = {}
    conns["fw"] = _conn(
        cc, "out1", boiler, "in1", "fw_boiler", **sv("fw_boiler", m_main, p_ms, t_hp_fw)
    )
    conns["ms"] = _conn(
        boiler,
        "out1",
        hpt1,
        "in1",
        "main_steam",
        p=p_ms,
        T=T_MAIN_STEAM_C,
        m=m_main,
        fluid={"water": 1},
    )
    conns["hpt1o"] = _conn(
        hpt1,
        "out1",
        hpt2,
        "in1",
        "hpt1_out",
        p=P_HP1_OUT_BAR * f,
        **sv("hpt1_out", m_main, P_HP1_OUT_BAR * f, 380),
    )
    conns["hpt2o"] = _conn(
        hpt2,
        "out1",
        sp_rh,
        "in1",
        "hpt2_out",
        p=p_rh,
        **sv("hpt2_out", m_main, p_rh, 330),
    )
    conns["to_rh"] = _conn(
        sp_rh,
        "out1",
        rh,
        "in1",
        "to_reheater",
        **sv("to_reheater", m_main * 0.85, p_rh, 330),
    )
    conns["hp_ext"] = _conn(
        sp_rh,
        "out2",
        hphtr,
        "in1",
        "hp_extraction",
        **sv("hp_extraction", m_main * 0.15, p_rh, 330),
    )
    conns["rh_out"] = _conn(
        rh,
        "out1",
        ipt,
        "in1",
        "reheat_out",
        T=T_REHEAT_C,
        **sv("reheat_out", m_main * 0.85, p_rh_out, 566),
    )
    conns["ipto"] = _conn(
        ipt,
        "out1",
        sp_ip,
        "in1",
        "ipt_out",
        **sv("ipt_out", m_main * 0.85, p_deaer, 280),
    )
    conns["to_lpt1"] = _conn(
        sp_ip,
        "out1",
        lpt1,
        "in1",
        "to_lpt1",
        **sv("to_lpt1", m_main * 0.8, p_deaer, 280),
    )
    conns["ip_ext"] = _conn(
        sp_ip,
        "out2",
        deaer,
        "in2",
        "ip_extraction",
        **sv("ip_extraction", m_main * 0.1, p_deaer, 280),
    )
    conns["lpt1o"] = _conn(
        lpt1,
        "out1",
        sp_lp,
        "in1",
        "lpt1_out",
        p=p_lp,
        **sv("lpt1_out", m_main * 0.8, p_lp, 150),
    )
    conns["to_lpt2"] = _conn(
        sp_lp, "out1", lpt2, "in1", "to_lpt2", **sv("to_lpt2", m_main * 0.7, p_lp, 150)
    )
    conns["lp_ext"] = _conn(
        sp_lp,
        "out2",
        lphtr,
        "in1",
        "lp_extraction",
        **sv("lp_extraction", m_main * 0.1, p_lp, 150),
    )
    conns["lpt2o"] = _conn(
        lpt2,
        "out1",
        m_cond,
        "in1",
        "lpt2_out",
        **sv("lpt2_out", m_main * 0.7, P_CONDENSER_BAR, 40),
    )
    conns["cond_in"] = _conn(
        m_cond,
        "out1",
        cond,
        "in1",
        "cond_in",
        p=P_CONDENSER_BAR,
        **sv("cond_in", m_main * 0.8, P_CONDENSER_BAR, 40),
    )
    conns["cond_out"] = _conn(
        cond,
        "out1",
        cpump,
        "in1",
        "cond_out",
        **sv("cond_out", m_main * 0.8, P_CONDENSER_BAR, 39),
    )
    conns["cp_o"] = _conn(
        cpump,
        "out1",
        lphtr,
        "in2",
        "cond_pump_out",
        **sv("cond_pump_out", m_main * 0.8, p_deaer, 45),
    )
    conns["lp_fw"] = _conn(
        lphtr,
        "out2",
        deaer,
        "in1",
        "lp_fw_out",
        T=t_lp_fw,
        **sv("lp_fw_out", m_main * 0.8, p_deaer, t_lp_fw),
    )
    conns["deaer_o"] = _conn(
        deaer,
        "out1",
        fpump,
        "in1",
        "deaer_out",
        p=p_deaer,
        x=0,
        **sv("deaer_out", m_main, p_deaer, 175),
    )
    conns["fp_o"] = _conn(
        fpump,
        "out1",
        hphtr,
        "in2",
        "feed_pump_out",
        **sv("feed_pump_out", m_main, P_FEED_PUMP_OUT_BAR * f, 180),
    )
    conns["hp_fw"] = _conn(
        hphtr,
        "out2",
        cc,
        "in1",
        "hp_fw_out",
        T=t_hp_fw,
        **sv("hp_fw_out", m_main, p_ms, t_hp_fw),
    )
    conns["hp_dr"] = _conn(
        hphtr,
        "out1",
        v_hp,
        "in1",
        "hp_drain",
        x=0,
        **sv("hp_drain", m_main * 0.15, p_rh, 250),
    )
    conns["hp_dr2"] = _conn(
        v_hp,
        "out1",
        deaer,
        "in3",
        "hp_drain_deaer",
        **sv("hp_drain_deaer", m_main * 0.15, p_deaer, 175),
    )
    conns["lp_dr"] = _conn(
        lphtr,
        "out1",
        v_lp,
        "in1",
        "lp_drain",
        x=0,
        **sv("lp_drain", m_main * 0.1, p_lp, 125),
    )
    conns["lp_dr2"] = _conn(
        v_lp,
        "out1",
        m_cond,
        "in2",
        "lp_drain_cond",
        **sv("lp_drain_cond", m_main * 0.1, P_CONDENSER_BAR, 39),
    )
    conns["cw_in"] = _conn(
        cw_src,
        "out1",
        cond,
        "in2",
        "cw_in",
        p=1.5,
        T=CW_IN_C,
        m0=15000,
        fluid={"water": 1},
    )
    conns["cw_out"] = _conn(
        cond, "out2", cw_sink, "in1", "cw_out", T=CW_OUT_C, m0=15000
    )
    nw.add_conns(*conns.values())
    comps = {
        "boiler": boiler,
        "hpt1": hpt1,
        "hpt2": hpt2,
        "rh": rh,
        "ipt": ipt,
        "lpt1": lpt1,
        "lpt2": lpt2,
        "cond": cond,
        "cpump": cpump,
        "lphtr": lphtr,
        "deaer": deaer,
        "fpump": fpump,
        "hphtr": hphtr,
    }
    return nw, conns, comps


def solve_point(
    load_fraction: float, m_main: float, start: dict | None = None
) -> DesignResult:
    """Solve one load point and reduce it to power / heat-rate figures.

    Raises
    ------
    RuntimeError
        If the TESPy network does not converge.
    """
    nw, conns, comps = build_network(load_fraction, m_main, start=start)
    nw.solve("design")
    if not nw.converged:
        raise RuntimeError(
            f"TESPy did not converge at load fraction {load_fraction} "
            f"with m_main={m_main} kg/s (status {nw.status})"
        )

    def kw(comp, attr="P"):
        return getattr(comp, attr).val_SI / 1000.0

    p_turb = -sum(kw(comps[k]) for k in ("hpt1", "hpt2", "ipt", "lpt1", "lpt2"))
    p_pump = sum(kw(comps[k]) for k in ("cpump", "fpump"))
    p_shaft = p_turb - p_pump
    p_gross = p_shaft * GENERATOR_EFFICIENCY
    eta_b = boiler_efficiency(load_fraction)
    aux = aux_rate(load_fraction)
    p_net = p_gross * (1.0 - aux)
    q_boiler = kw(comps["boiler"], "Q")
    q_reheat = kw(comps["rh"], "Q")
    q_steam = q_boiler + q_reheat
    q_cond = -kw(comps["cond"], "Q")
    # Steam-side heat rate (the paper's definition): steam heat absorbed
    # in boiler + reheater per kWh generated.
    hr_steam = q_steam / p_gross * 3600.0
    hr_fuel = hr_steam / eta_b
    eta_cycle = p_gross / q_steam
    # Standard-coal consumption, g/kWh (paper's formula, LHV 29.27 MJ/kg).
    coal_gen = hr_fuel / PIPING_EFFICIENCY / 29.27
    coal_supply = coal_gen / (1.0 - aux)
    # Independent energy-balance check: steam heat in = shaft work +
    # condenser heat rejected (+ pump work, which enters the cycle).
    residual = q_steam - (p_shaft + q_cond)

    states = {
        label: (
            c.m.val_SI,
            c.p.val_SI / 1e5,
            c.T.val_SI - 273.15,
            c.h.val_SI / 1000.0,
        )
        for label, c in conns.items()
    }
    return DesignResult(
        load_fraction=load_fraction,
        main_steam_flow_kg_per_s=m_main,
        net_power_kw=p_net,
        gross_power_kw=p_gross,
        shaft_power_kw=p_shaft,
        pump_power_kw=p_pump,
        boiler_heat_kw=q_boiler,
        reheat_heat_kw=q_reheat,
        steam_heat_kw=q_steam,
        condenser_heat_kw=q_cond,
        heat_rate_steam=hr_steam,
        heat_rate_fuel=hr_fuel,
        cycle_efficiency=eta_cycle,
        boiler_efficiency=eta_b,
        aux_rate=aux,
        coal_gen_g_per_kwh=coal_gen,
        coal_supply_g_per_kwh=coal_supply,
        feedwater_temp_c=conns["hp_fw"].T.val_SI - 273.15,
        main_steam_pressure_bar=conns["ms"].p.val_SI / 1e5,
        reheat_pressure_bar=conns["rh_out"].p.val_SI / 1e5,
        condenser_pressure_bar=P_CONDENSER_BAR,
        extraction_hp_kg_per_s=conns["hp_ext"].m.val_SI,
        extraction_ip_kg_per_s=conns["ip_ext"].m.val_SI,
        extraction_lp_kg_per_s=conns["lp_ext"].m.val_SI,
        energy_balance_residual_kw=residual,
        converged=True,
        states=states,
    )


def calibrate_design(
    m_guess: float = 550.0, tol_kw: float = 500.0, max_iter: int = 6
) -> DesignResult:
    """Find the main-steam flow that yields 630 MW net at full load.

    Secant iteration on the net power; the design point is defined by net
    (not gross) power, with the measured 630 MW auxiliary rate of 5.26%.
    """
    m0, m1 = m_guess * 0.95, m_guess * 1.05
    r0 = solve_point(1.0, m0)
    r1 = solve_point(1.0, m1)
    for _ in range(max_iter):
        err1 = r1.net_power_kw - RATED_NET_POWER_KW
        if abs(err1) <= tol_kw:
            return r1
        err0 = r0.net_power_kw - RATED_NET_POWER_KW
        slope = (err1 - err0) / (m1 - m0)
        if slope == 0:
            raise RuntimeError("calibration secant slope is zero")
        m2 = m1 - err1 / slope
        r0, m0, r1, m1 = r1, m1, solve_point(1.0, m2), m2
    if abs(r1.net_power_kw - RATED_NET_POWER_KW) > tol_kw:
        raise RuntimeError(
            f"calibration did not reach 630 MW: got {r1.net_power_kw / 1000:.1f} MW"
        )
    return r1

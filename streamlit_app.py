"""Pump sizing calculator: Flow (Q) and Total Dynamic Head (TDH). Streamlit version."""
from math import ceil, log10, pi

import pandas as pd
import streamlit as st

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from theme import page_setup
except ImportError:                      # theme.py missing: fall back to a plain page
    def page_setup(title, subtitle="", icon="💧"):
        st.set_page_config(page_title=title, page_icon=icon, layout="wide")
        st.title(title)

page_setup("Pump Sizing Calculator")


# ------------------------------------------------------------------ data
OD_INCH = {20: '1/2"', 25: '3/4"', 32: '1"', 40: '1 1/4"', 50: '1 1/2"',
           63: '2"', 75: '2 1/2"', 90: '3"', 110: '4"'}

# HDPE (PE100) pressure classes. The SDR (outer diameter / wall thickness) is used inside the app only.
CLASSES = {"PN4": 41, "PN5": 33, "PN6": 26, "PN8": 21, "PN10": 17,
           "PN12.5": 13.6, "PN16": 11, "PN20": 9, "PN25": 7.4}

# material: (Hazen-Williams C, absolute roughness in mm for Darcy-Weisbach)
# Typical textbook values: edit them if your supplier/design standard differs.
MATERIALS = {
    "HDPE": (150, 0.0015), "LDPE": (150, 0.0015), "uPVC": (150, 0.0015),
    "Rubber lined": (140, 0.01), "New steel": (140, 0.045),
    "Medium steel": (120, 0.15), "Corroded steel": (100, 0.6),
    "Galvanized iron": (120, 0.15), "Glass": (140, 0.0015), "Lead": (130, 0.0015),
}

# ------------------------------------------------------------------ unit tables
VOL_TO_L = {"litres/day": 1, "m³/day": 1000, "US gallons/day": 3.78541, "Imp. gallons/day": 4.54609}
LEN_TO_M = {"m": 1, "ft": 0.3048, "yd": 0.9144, "km": 1000}
FLOW_FROM_M3H = {"m³/h": 1, "L/min": 1000 / 60, "L/s": 1000 / 3600, "m³/min": 1 / 60,
                 "L/h": 1000, "m³/day": 24, "US GPM": 4.40287}
PRESSURE_FROM_KPA = {"bar": 0.01, "kPa": 1.0, "psi": 0.145038, "MPa": 0.001,
                     "atm": 0.00986923, "kgf/cm²": 0.0101972}
HEAD_FROM_M = {"m": 1, "ft": 3.28084, "bar": 0.0980665, "kPa": 9.80665, "psi": 1.42233}
G = 9.81

# ------------------------------------------------------------------ display switches
# Everything below still exists in the app. Set a switch to True to show it again.
SHOW_UNIT_SELECTORS = False    # "Display units" dropdowns (flow unit, head/pressure unit)
SHOW_PIPE_SUMMARY = False      # "Selected pipe: ..." line under Total Dynamic Head
SHOW_WATER_TEMP = False        # water temperature input (used by the Darcy-Weisbach method)
SHOW_MOTOR = False             # "Motor estimate" section
SHOW_WALL_AND_ID = False       # Wall and ID columns in the pipe comparison table
FITTINGS_ALLOWANCE_PCT = 0.0   # extra % added to friction loss for fittings (0 = pure pipe friction)


# ------------------------------------------------------------------ compatibility helpers
def full_width(fn, *args, **kwargs):
    """Call st.dataframe / st.data_editor so it works on old AND new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)           # Streamlit >= 1.50
    except (TypeError, st.errors.StreamlitAPIException):
        return fn(*args, use_container_width=True, **kwargs)  # older versions



# ------------------------------------------------------------------ hydraulics
def wall_mm(od, sdr):
    return max(ceil(od / sdr * 10) / 10, 1.8)       # approx. wall thickness


def hazen_williams(q_m3h, length, d_m, c):
    q = q_m3h / 3600
    return 10.67 * length * q ** 1.852 / (c ** 1.852 * d_m ** 4.87)


def water_props(temp_c):
    mu = 2.414e-5 * 10 ** (247.8 / (temp_c + 133.15))      # Pa.s
    rho = 1000 * (1 - (temp_c - 4) ** 2 / 119000)           # kg/m3 (approx.)
    return rho, mu


def darcy_weisbach(q_m3h, length, d_m, k_mm, temp_c):
    rho, mu = water_props(temp_c)
    area = pi * d_m ** 2 / 4
    v = q_m3h / 3600 / area
    re = rho * v * d_m / mu
    if re < 2300:
        f = 64 / max(re, 1e-9)
    else:                                                    # Swamee-Jain (explicit Colebrook)
        f = 0.25 / log10(k_mm / 1000 / (3.7 * d_m) + 5.74 / re ** 0.9) ** 2
    return f * length / d_m * v ** 2 / (2 * G), f, re


def friction(q, length, d_m, method, c, k_mm, temp):
    if method.startswith("Hazen"):
        return hazen_williams(q, length, d_m, c), None, None
    return darcy_weisbach(q, length, d_m, k_mm, temp)


# ------------------------------------------------------------------ UI helpers
def length_input(label, default, key, min_value=0.0):
    col1, col2 = st.columns([2, 1])
    val = col1.number_input(label, min_value=min_value, value=default, step=0.5, key=key)
    unit = col2.selectbox("Unit", list(LEN_TO_M), key=key + "_u")
    return val * LEN_TO_M[unit]



with st.sidebar:
    st.header("Water requirement")
    c1, c2 = st.columns([2, 1])
    vol = c1.number_input("Daily water requirement", 0.0, value=10000.0, step=500.0)
    vol_u = c2.selectbox("Unit", list(VOL_TO_L), key="vol_u")
    hours = st.number_input("Pumping hours per day", 0.5, 24.0, 5.0, 0.5)

    st.header("Heights and distances")
    depth = length_input("Depth of water source", 30.0, "depth")
    elev = length_input("Elevation, source to tank", 5.0, "elev", min_value=-1000.0)
    dist = length_input("Horizontal distance, source to tank", 100.0, "dist")
    tank_h = length_input("Height of tank", 2.0, "tank")
    stand = length_input("Tank stand height", 3.0, "stand")

    st.header("Pipe")
    material = st.selectbox("Pipe material", list(MATERIALS), index=0)
    cls = st.selectbox("Pressure class (PN)", list(CLASSES), index=list(CLASSES).index("PN10"),
                       help="Thicker wall = smaller inside diameter = more friction. "
                            "Used for plastic pipes sold by outer diameter.")
    pipe_choice = st.selectbox("Pipe size (outer diameter)",
                               ["Auto (smallest within velocity limit)"] +
                               [f"{mm} mm ({OD_INCH[mm]})" for mm in OD_INCH] +
                               ["Custom inside diameter"])
    custom_id = None
    if pipe_choice.startswith("Custom"):
        custom_id = st.number_input("Inside diameter (mm)", 5.0, 500.0, 25.0, 0.1)

    st.header("Friction method")
    method = st.selectbox("Method", ["Hazen-Williams", "Darcy-Weisbach (Moody / Swamee-Jain)"])
    c_default, k_default = MATERIALS[material]
    c_val = st.number_input("Hazen-Williams C", 50.0, 160.0, float(c_default), 1.0)
    k_val = st.number_input("Roughness k (mm), for Darcy-Weisbach", 0.0, 5.0, float(k_default), 0.0005, format="%.4f")
    temp = st.number_input("Water temperature (°C)", 0.0, 90.0, 25.0, 1.0) if SHOW_WATER_TEMP else 25.0
    minor = FITTINGS_ALLOWANCE_PCT
    vmax = st.number_input("Max velocity (m/s)", 0.5, 4.0, 1.5, 0.1)
    eff = st.number_input("Pump efficiency (%)", 10.0, 90.0, 50.0)

    if SHOW_UNIT_SELECTORS:
        st.header("Display units")
        flow_u = st.selectbox("Flow unit", list(FLOW_FROM_M3H), index=0)
        head_u = st.selectbox("Head / pressure unit", list(HEAD_FROM_M), index=0)
    else:
        flow_u, head_u = "m³/h", "m"

# ------------------------------------------------------------------ input checks
if vol <= 0:
    st.warning("Enter a daily water requirement greater than zero to see results.")
    st.stop()
if depth + dist + tank_h + stand <= 0:
    st.warning("Pipe length is zero. Enter the depth, distance, tank height and stand height.")
    st.stop()

# ------------------------------------------------------------------ calculations
daily_l = vol * VOL_TO_L[vol_u]
q = daily_l / 1000 / hours                                   # m3/h
static = depth + elev + tank_h + stand                       # m
length = depth + dist + tank_h + stand                       # m
sdr = CLASSES[cls]

rows = []
for od in OD_INCH:
    w = wall_mm(od, sdr)
    d_m = (od - 2 * w) / 1000
    hf, f, re = friction(q, length, d_m, method, c_val, k_val, temp)
    hf *= 1 + minor / 100
    v = q / 3600 / (pi * d_m ** 2 / 4)
    rows.append({"ext": od, "Pipe": f"{od} mm ({OD_INCH[od]})", "Wall (mm)": w,
                 "ID (mm)": round(d_m * 1000, 1), "Velocity (m/s)": round(v, 2),
                 "Friction (m)": round(hf, 2), "TDH (m)": round(static + hf, 2),
                 "OK": v <= vmax, "f": f, "Re": re, "hf": hf})
df = pd.DataFrame(rows)

if custom_id:
    d_m = custom_id / 1000
    hf, f, re = friction(q, length, d_m, method, c_val, k_val, temp)
    hf *= 1 + minor / 100
    v = q / 3600 / (pi * d_m ** 2 / 4)
    sel = {"Pipe": f"Custom ID {custom_id} mm", "ID (mm)": custom_id, "Velocity (m/s)": round(v, 2),
           "Friction (m)": round(hf, 2), "TDH (m)": round(static + hf, 2), "OK": v <= vmax, "f": f, "Re": re,
           "hf": hf}
elif pipe_choice.startswith("Auto"):
    ok = df[df["OK"]]
    sel = (ok.iloc[0] if not ok.empty else df.iloc[-1]).to_dict()
else:
    sel = df[df["ext"] == int(pipe_choice.split()[0])].iloc[0].to_dict()

tdh = sel["TDH (m)"]
hyd_kw = 1000 * G * (q / 3600) * tdh / 1000
motor_kw = hyd_kw / (eff / 100) * 1.2


def head_fmt(m, dp=2):
    return f"{m * HEAD_FROM_M[head_u]:.{dp}f} {head_u}"


hf_exact = sel["hf"]                              # friction head loss, metres of water
loss_kpa = hf_exact * 1000 * G / 1000             # pressure loss = rho * g * h
loss_bar = loss_kpa / 100
loss_psi = loss_kpa * 0.145038


# ------------------------------------------------------------------ display
st.subheader("Flow rate (Q)")
cols = st.columns(4)
cols[0].metric(f"Q ({flow_u})", f"{q * FLOW_FROM_M3H[flow_u]:.3f}")
cols[1].metric("L/min", f"{q * FLOW_FROM_M3H['L/min']:.3f}")
cols[2].metric("L/s", f"{q * FLOW_FROM_M3H['L/s']:.3f}")
cols[3].metric("L/day", f"{daily_l:,.0f}")

st.subheader("Total Dynamic Head")
cols = st.columns(4)
cols[0].metric("TDH", head_fmt(tdh))
cols[1].metric("Static head", head_fmt(static))
cols[2].metric("Friction head loss", head_fmt(hf_exact, 4))
cols[3].metric("Pipe length L", f"{length / LEN_TO_M['m']:.1f} m")
pc = st.columns([1, 2])
p_unit = pc[0].selectbox("Pressure unit", list(PRESSURE_FROM_KPA), index=0)
pf = PRESSURE_FROM_KPA[p_unit]
pc[1].metric("Pressure loss", f"{loss_kpa * pf:.4f} {p_unit}")
tag = "Recommended" if pipe_choice.startswith("Auto") else "Selected"
if SHOW_PIPE_SUMMARY:
    st.info(f"{tag} pipe: **{sel['Pipe']}** ({material}, {cls}) · inside diameter {sel['ID (mm)']} mm · "
            f"velocity {sel['Velocity (m/s)']} m/s")
if not sel["OK"]:
    st.warning("Velocity is above your limit for this pipe. Try a larger size.")

if SHOW_MOTOR:
    st.subheader("Motor estimate")
    a, b = st.columns(2)
    a.metric("Hydraulic power", f"{hyd_kw:.2f} kW")
    b.metric("Suggested motor (+20% margin)", f"{motor_kw:.2f} kW", f"≈ {motor_kw * 1.341:.2f} HP", delta_color="off")

st.subheader("All pipe sizes compared")
hide_cols = ["ext", "f", "Re", "hf"] + ([] if SHOW_WALL_AND_ID else ["Wall (mm)", "ID (mm)"])
show = df.drop(columns=hide_cols).copy()
show["OK"] = show["OK"].map({True: "✔", False: "✖"})
full_width(st.dataframe, show, hide_index=True)

with st.expander("Show the calculation"):
    st.write(f"**Q** = {daily_l:,.0f} L/day ÷ 1000 ÷ {hours} h = **{q:.3f} m³/h**")
    st.write(f"**Static head** = depth + elevation + tank height + stand = **{static:.2f} m**")
    st.write(f"**L** = depth + distance + tank height + stand = **{length:.2f} m**")
    if method.startswith("Hazen"):
        st.latex(r"h_f = \frac{10.67\,L\,Q^{1.852}}{C^{1.852}\,D^{4.87}}")
        st.write(f"C = {c_val:g}, D = {sel['ID (mm)']} mm (Q in m³/s, D and L in metres)")
    else:
        st.latex(r"h_f = f\,\frac{L}{D}\,\frac{v^2}{2g}")
        if sel["f"]:
            st.write(f"Reynolds number = {sel['Re']:,.0f}, Darcy friction factor f = {sel['f']:.4f}, k = {k_val} mm")
    if minor:
        st.write(f"Friction loss includes a {minor:g}% allowance for fittings.")
    st.write(f"**Friction head loss** = {hf_exact:.4f} m of water")
    st.write(f"**Pressure loss** = ρ·g·h = 1000 × 9.81 × {hf_exact:.4f} = {loss_kpa * 1000:,.0f} Pa = **{loss_bar:.4f} bar**")
    st.write(f"**TDH = {static:.2f} + {hf_exact:.2f} = {tdh:.2f} m**")

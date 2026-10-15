"""
PEC - Pump Sizing & Irrigation Design Tool  (single file, no other files needed)

Run:      pip install -r requirements.txt
          streamlit run app.py
Tools:    1) Pump Sizing  2) Water Demand  3) Pumping Main (TDH by sections)
"""
import base64
import io
from math import ceil, floor, log10, pi

import pandas as pd
import streamlit as st

# ============================================================ display switches
# Everything below still exists in the app. Set a switch to True to show it again.
SHOW_UNIT_SELECTORS = False    # flow-unit and head-unit dropdowns
SHOW_PIPE_SUMMARY = False      # "Selected pipe: ..." line
SHOW_MOTOR = False             # motor estimate
SHOW_WALL_AND_ID = False       # wall / ID columns in the pipe comparison table
SHOW_WATER_TEMP = False        # water temperature input (Darcy-Weisbach only)
FITTINGS_ALLOWANCE_PCT = 0.0   # extra % on friction loss for fittings (0 = pure pipe friction)
WATER_TEMP_C = 25.0

# ============================================================ data
OD_INCH = {20: '1/2"', 25: '3/4"', 32: '1"', 40: '1 1/4"', 50: '1 1/2"',
           63: '2"', 75: '2 1/2"', 90: '3"', 110: '4"'}

# PE100 pressure classes -> SDR (used inside the app to get the wall thickness)
CLASSES = {"PN4": 41, "PN5": 33, "PN6": 26, "PN8": 21, "PN10": 17,
           "PN12.5": 13.6, "PN16": 11, "PN20": 9, "PN25": 7.4}

# material: (Hazen-Williams C, roughness k in mm)
MATERIALS = {
    "HDPE": (150, 0.0015), "LDPE": (150, 0.0015), "uPVC": (150, 0.0015),
    "Rubber lined": (140, 0.01), "New steel": (140, 0.045),
    "Medium steel": (120, 0.15), "Corroded steel": (100, 0.6),
    "Galvanized iron": (120, 0.15), "Glass": (140, 0.0015), "Lead": (130, 0.0015),
}

VOL_TO_L = {"litres/day": 1, "m³/day": 1000, "US gallons/day": 3.78541, "Imp. gallons/day": 4.54609}
LEN_TO_M = {"m": 1, "ft": 0.3048, "yd": 0.9144, "km": 1000}
FLOW_FROM_M3H = {"m³/h": 1, "L/min": 1000 / 60, "L/s": 1000 / 3600, "m³/min": 1 / 60,
                 "L/h": 1000, "m³/day": 24, "US GPM": 4.40287}
HEAD_FROM_M = {"m": 1, "ft": 3.28084, "bar": 0.0980665, "kPa": 9.80665, "psi": 1.42233}
PRESSURE_FROM_KPA = {"bar": 0.01, "kPa": 1.0, "psi": 0.145038, "MPa": 0.001,
                     "atm": 0.00986923, "kgf/cm²": 0.0101972}
G = 9.81

# crop: (peak Kc, root depth m, allowable depletion p)
CROPS = {"Tomato": (1.15, 1.0, 0.5), "Cabbage": (1.05, 0.5, 0.45), "Carrot": (1.05, 0.6, 0.5),
         "Cauliflower": (1.05, 0.6, 0.5), "Onion": (1.05, 0.6, 0.5), "Garlic": (1.0, 0.6, 0.5),
         "Egg plant": (1.05, 0.6, 0.5), "Peppers": (1.05, 0.8, 0.5), "Cucumber": (1.0, 0.6, 0.5),
         "Water melons": (1.0, 0.4, 0.5), "Beans": (1.15, 0.4, 0.6), "Cotton": (1.2, 1.0, 0.9),
         "Coffee": (1.1, 0.9, 0.5), "Maize": (1.2, 0.9, 0.8), "Millet": (1.0, 1.0, 0.7),
         "Rice": (1.2, 0.5, 0.5), "Banana": (1.2, 0.5, 0.55), "Pumpkin": (1.0, 0.6, 0.5)}
LTU = {"Cattle": 0.7, "Goats": 0.15, "Sheep": 0.15, "Pigs": 0.4, "Poultry": 0.1}

# ============================================================ look and feel (PEC logo colours)
CSS = """
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 1.4rem; max-width: 1180px;}
[data-testid="stSidebar"] {background: linear-gradient(180deg, #031B45 0%, #000E28 100%);
    border-right: 2px solid #015FBF;}
[data-testid="stSidebar"] label, [data-testid="stSidebar"] label p, [data-testid="stSidebar"] label span,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color: #F6F6F6 !important;}
[data-testid="stSidebar"] h2 {color: #FE7C00 !important; font-size: 1.05rem; letter-spacing: .04em;
    text-transform: uppercase; border-bottom: 1px solid #015FBF; padding-bottom: .3rem;}
.pec-hero {display: flex; align-items: center; gap: 22px; padding: 18px 26px; margin-bottom: 18px;
    background: linear-gradient(120deg, #000E28 0%, #04265E 60%, #015FBF 140%);
    border: 1px solid #0B3A80; border-bottom: 4px solid #FE7C00; border-radius: 16px;
    box-shadow: 0 6px 22px rgba(1, 95, 191, .25);}
.pec-hero img {height: 104px; width: auto; border-radius: 12px;}
.pec-hero h1 {margin: 0; padding: 0; font-size: 2rem; line-height: 1.15; color: #F6F6F6;}
.pec-hero p {margin: 6px 0 0; color: #8FB8FF; letter-spacing: .12em; font-size: .9rem; text-transform: uppercase;}
.pec-hero p b {color: #FE7C00;}
@media (max-width: 640px) {.pec-hero {flex-direction: column; text-align: center;} .pec-hero h1 {font-size: 1.5rem;}}
h3 {border-left: 5px solid #FE7C00; padding-left: 12px !important; margin-top: .8rem;}
[data-testid="stMetric"] {background: linear-gradient(135deg, #04204D 0%, #021433 100%);
    border: 1px solid #0B3A80; border-left: 5px solid #FE7C00; border-radius: 12px;
    padding: 14px 16px; box-shadow: 0 3px 12px rgba(0, 0, 0, .3);}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] p {color: #8FB8FF !important; font-size: .85rem;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {color: #F6F6F6 !important; font-weight: 700;}
[data-testid="stAlert"] {border-radius: 12px;}
</style>
"""


def setup_page():
    icon = "💧"
    try:
        from PIL import Image
        icon = Image.open(io.BytesIO(base64.b64decode(LOGO_B64)))
    except Exception:
        pass
    st.set_page_config(page_title="PEC Pump & Irrigation Calculator", page_icon=icon, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title):
    st.markdown(
        f'<div class="pec-hero"><img src="data:image/png;base64,{LOGO_B64}" alt="PEC">'
        f'<div><h1>{title}</h1><p>Precision <b>•</b> Engineering <b>•</b> Crop Irrigation</p></div></div>',
        unsafe_allow_html=True)


def full_width(fn, *args, **kwargs):
    """st.dataframe / st.data_editor that works on old AND new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)
    except (TypeError, st.errors.StreamlitAPIException):
        return fn(*args, use_container_width=True, **kwargs)


# ============================================================ hydraulics
def wall_mm(od, sdr):
    return max(ceil(od / sdr * 10) / 10, 1.8)


def hazen_williams(q_m3h, length, d_m, c):
    q = q_m3h / 3600
    return 10.67 * length * q ** 1.852 / (c ** 1.852 * d_m ** 4.87)


def water_props(temp_c):
    mu = 2.414e-5 * 10 ** (247.8 / (temp_c + 133.15))
    rho = 1000 * (1 - (temp_c - 4) ** 2 / 119000)
    return rho, mu


def darcy_weisbach(q_m3h, length, d_m, k_mm, temp_c):
    rho, mu = water_props(temp_c)
    v = q_m3h / 3600 / (pi * d_m ** 2 / 4)
    re = rho * v * d_m / mu
    if re < 2300:
        f = 64 / max(re, 1e-9)
    else:
        f = 0.25 / log10(k_mm / 1000 / (3.7 * d_m) + 5.74 / re ** 0.9) ** 2
    return f * length / d_m * v ** 2 / (2 * G), f, re


def friction(q, length, d_m, method, c, k_mm, temp):
    if method.startswith("Hazen"):
        return hazen_williams(q, length, d_m, c), None, None
    return darcy_weisbach(q, length, d_m, k_mm, temp)


def length_input(label, default, key, min_value=0.0):
    col1, col2 = st.columns([2, 1])
    val = col1.number_input(label, min_value=min_value, value=default, step=0.5, key=key)
    unit = col2.selectbox("Unit", list(LEN_TO_M), key=key + "_u")
    return val * LEN_TO_M[unit]


# ============================================================ tool 1: pump sizing
def pump_sizing():
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
        cls = st.selectbox("Pressure class (PN)", list(CLASSES), index=list(CLASSES).index("PN10"))
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
        k_val = st.number_input("Roughness k (mm), for Darcy-Weisbach", 0.0, 5.0, float(k_default),
                                0.0005, format="%.4f")
        temp = (st.number_input("Water temperature (°C)", 0.0, 90.0, WATER_TEMP_C, 1.0)
                if SHOW_WATER_TEMP else WATER_TEMP_C)
        minor = FITTINGS_ALLOWANCE_PCT
        vmax = st.number_input("Max velocity (m/s)", 0.5, 4.0, 1.5, 0.1)
        eff = st.number_input("Pump efficiency (%)", 10.0, 90.0, 50.0)

        if SHOW_UNIT_SELECTORS:
            st.header("Display units")
            flow_u = st.selectbox("Flow unit", list(FLOW_FROM_M3H), index=0)
            head_u = st.selectbox("Head / pressure unit", list(HEAD_FROM_M), index=0)
        else:
            flow_u, head_u = "m³/h", "m"

    if vol <= 0:
        st.warning("Enter a daily water requirement greater than zero to see results.")
        return
    if depth + dist + tank_h + stand <= 0:
        st.warning("Pipe length is zero. Enter the depth, distance, tank height and stand height.")
        return

    daily_l = vol * VOL_TO_L[vol_u]
    q = daily_l / 1000 / hours
    static = depth + elev + tank_h + stand
    length = depth + dist + tank_h + stand
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
               "Friction (m)": round(hf, 2), "TDH (m)": round(static + hf, 2), "OK": v <= vmax,
               "f": f, "Re": re, "hf": hf}
    elif pipe_choice.startswith("Auto"):
        ok = df[df["OK"]]
        sel = (ok.iloc[0] if not ok.empty else df.iloc[-1]).to_dict()
    else:
        sel = df[df["ext"] == int(pipe_choice.split()[0])].iloc[0].to_dict()

    tdh = sel["TDH (m)"]
    hf_exact = sel["hf"]
    loss_kpa = hf_exact * 1000 * G / 1000          # pressure loss = rho * g * h
    loss_bar = loss_kpa / 100
    hyd_kw = 1000 * G * (q / 3600) * tdh / 1000
    motor_kw = hyd_kw / (eff / 100) * 1.2

    def head_fmt(m, dp=2):
        return f"{m * HEAD_FROM_M[head_u]:.{dp}f} {head_u}"

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
    cols[3].metric("Pipe length L", f"{length:.1f} m")

    pc = st.columns([1, 2])
    p_unit = pc[0].selectbox("Pressure unit", list(PRESSURE_FROM_KPA), index=0)
    pc[1].metric("Pressure loss", f"{loss_kpa * PRESSURE_FROM_KPA[p_unit]:.4f} {p_unit}")

    if SHOW_PIPE_SUMMARY:
        tag = "Recommended" if pipe_choice.startswith("Auto") else "Selected"
        st.info(f"{tag} pipe: **{sel['Pipe']}** ({material}, {cls}) · inside diameter {sel['ID (mm)']} mm · "
                f"velocity {sel['Velocity (m/s)']} m/s")
    if not sel["OK"]:
        st.warning("Velocity is above your limit for this pipe. Try a larger size.")

    if SHOW_MOTOR:
        st.subheader("Motor estimate")
        a, b = st.columns(2)
        a.metric("Hydraulic power", f"{hyd_kw:.2f} kW")
        b.metric("Suggested motor (+20% margin)", f"{motor_kw:.2f} kW", f"≈ {motor_kw * 1.341:.2f} HP",
                 delta_color="off")

    st.subheader("All pipe sizes compared")
    hide = ["ext", "f", "Re", "hf"] + ([] if SHOW_WALL_AND_ID else ["Wall (mm)", "ID (mm)"])
    show = df.drop(columns=hide).copy()
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
                st.write(f"Reynolds number = {sel['Re']:,.0f}, friction factor f = {sel['f']:.4f}, k = {k_val} mm")
        if minor:
            st.write(f"Friction loss includes a {minor:g}% allowance for fittings.")
        st.write(f"**Friction head loss** = {hf_exact:.4f} m of water")
        st.write(f"**Pressure loss** = ρ·g·h = 1000 × 9.81 × {hf_exact:.4f} = "
                 f"{loss_kpa * 1000:,.0f} Pa = **{loss_bar:.4f} bar**")
        st.write(f"**TDH = {static:.2f} + {hf_exact:.2f} = {tdh:.2f} m**")


# ============================================================ tool 2: water demand
def water_demand():
    st.caption("Crop water requirement → net and gross depth → daily volume → pumping flow.")
    left, right = st.columns(2)
    with left:
        st.subheader("Crop and climate")
        crop = st.selectbox("Design crop", list(CROPS))
        kc0, zr0, p0 = CROPS[crop]
        kc = st.number_input("Kc (mid season)", 0.1, 2.0, kc0, 0.05, key=f"kc{crop}")
        eto = st.number_input("Peak ETo (mm/day)", 0.0, 12.0, 4.84, 0.01)
        rain = st.number_input("Effective rain in that month (mm/day)", 0.0, 20.0, 0.23, 0.01)
        etc = max(eto * kc - rain, 0.01)
        st.metric("Crop water requirement (ETc − rain)", f"{etc:.2f} mm/day")

        st.subheader("Soil")
        fc = st.number_input("Field capacity (m³/m³)", 0.05, 0.6, 0.285, 0.005, format="%.3f")
        pwp = st.number_input("Permanent wilting point (m³/m³)", 0.01, 0.5, 0.19, 0.005, format="%.3f")
        p = st.number_input("Allowable depletion, p", 0.1, 1.0, p0, 0.05, key=f"p{crop}")
        zr = st.number_input("Effective root depth Zr (m)", 0.1, 3.0, 0.6, 0.1, key=f"zr{crop}",
                             help=f"Table value for {crop}: {zr0} m.")
    with right:
        st.subheader("System")
        area = st.number_input("Command area (ha)", 0.1, 1000.0, 5.0, 0.5)
        eff = st.number_input("Application efficiency", 0.3, 1.0, 0.85, 0.05)
        pr = st.number_input("Sprinkler / rainspray precipitation rate (mm/hr)", 1.0, 100.0, 15.0, 1.0)
        infil = st.number_input("Soil infiltration rate (mm/hr)", 1.0, 100.0, 25.0, 1.0)
        st.subheader("Livestock")
        counts = {a: st.number_input(f"{a} (number)", 0, 100000, v, key=f"n_{a}")
                  for a, v in zip(LTU, [200, 100, 50, 50, 0])}
        deficit = st.number_input("Irrigation supplied under deficit irrigation (%)", 10, 100, 50)
        hours = st.number_input("Pumping hours per day", 1.0, 24.0, 7.0, 0.5, key="wd_hours")

    aw = (fc - pwp) * 1000
    dnet = aw * p * zr
    freq = dnet / etc
    fa = st.number_input("Adopted irrigation frequency (days)", 1, 30, 4,
                         help="Keep it at or below the maximum frequency shown below.")
    dnet_c = fa * etc
    dgross = dnet_c / eff
    shift = dgross / pr
    irr_m3 = dgross * 10 * (area / fa)                  # 1 mm on 1 ha = 10 m3
    live_m3 = sum(n * LTU[a] * 50 for a, n in counts.items()) / 1000
    full = irr_m3 + live_m3
    deficit_m3 = irr_m3 * deficit / 100 + live_m3
    flow = deficit_m3 / hours

    st.divider()
    a, b, c, d = st.columns(4)
    a.metric("Net depth dnet", f"{dnet:.1f} mm")
    b.metric("Max frequency", f"{freq:.2f} days")
    c.metric("Gross depth", f"{dgross:.1f} mm")
    d.metric("Time per set", f"{shift:.2f} h")
    a, b, c, d = st.columns(4)
    a.metric("Irrigation", f"{irr_m3:.1f} m³/day")
    b.metric("Livestock", f"{live_m3:.2f} m³/day")
    c.metric("Total (full irrigation)", f"{full:.1f} m³/day")
    d.metric(f"Total ({deficit}% irrigation)", f"{deficit_m3:.1f} m³/day")
    st.success(f"Design pumping flow = {deficit_m3:.1f} m³/day ÷ {hours:g} h = **{flow:.2f} m³/h** "
               f"({flow * 1000 / 60:.0f} L/min, {flow / 3.6:.2f} L/s)")
    if fa > freq:
        st.warning("The adopted frequency is longer than the maximum frequency: the crop may be stressed.")
    if pr > infil:
        st.warning("Precipitation rate exceeds the soil infiltration rate: expect runoff.")
    st.session_state["demand"] = {"m3_day": deficit_m3, "hours": hours, "flow": flow}
    st.caption("Open **Pumping Main (TDH)** in the menu: it picks up this flow automatically.")


# ============================================================ tool 3: pumping main by sections
def pumping_main():
    st.caption("Friction per section: hf = 6.824·L·(V/C)^1.852·D^-1.167 (Hazen-Williams).")
    demand = st.session_state.get("demand")
    default_flow = round(demand["flow"], 2) if demand else 23.74

    top = st.columns(3)
    q = top[0].number_input("Pumping flow (m³/h)", 0.1, 5000.0, default_flow, 0.1,
                            help="Filled from the Water Demand tool when available.")
    eff = top[1].number_input("Overall pump + motor efficiency", 0.2, 0.95, 0.75, 0.05)
    minor = top[2].number_input("Fittings loss (% of friction)", 0.0, 100.0, 10.0)

    st.subheader("Sections (edit the table)")
    st.caption("ID = true inside diameter in mm. Extra head = residual pressure, filter loss, etc.")
    base = pd.DataFrame([
        ["1 Riser (pump to ground)", 3.7, 6.0, 80.0, 150.0, 0.0],
        ["2 Sump GL to pump house", 7.1, 650.0, 96.8, 120.0, 0.0],
        ["3 Pump house to reservoir GL", 3.2, 226.0, 96.8, 140.0, 0.0],
        ["4 Tower + tank to inlet", 14.7, 14.7, 80.0, 120.0, 12.0],
    ], columns=["Section", "Static lift (m)", "Length (m)", "ID (mm)", "C", "Extra head (m)"])
    edited = full_width(st.data_editor, base, num_rows="dynamic", hide_index=True)

    rows, skipped = [], 0
    for _, r in edited.iterrows():
        try:
            length, d_mm, c = float(r["Length (m)"]), float(r["ID (mm)"]), float(r["C"])
            st_i, extra = float(r["Static lift (m)"]), float(r["Extra head (m)"])
        except (TypeError, ValueError):
            skipped += 1
            continue
        if pd.isna(length + d_mm + c + st_i + extra) or min(length, d_mm, c) <= 0:
            skipped += 1
            continue
        d = d_mm / 1000
        v = (q / 3600) / (pi * d * d / 4)
        hf = length * 6.824 * (v / c) ** 1.852 * d ** -1.167
        fit = hf * minor / 100
        rows.append({"Section": r["Section"], "Velocity (m/s)": round(v, 2), "Friction (m)": round(hf, 2),
                     "Fittings (m)": round(fit, 2), "Static (m)": st_i, "Extra (m)": extra,
                     "Total head (m)": round(hf + fit + st_i + extra, 2)})
    if skipped:
        st.warning(f"{skipped} row(s) ignored: length, ID or C is empty or not above zero.")
    if not rows:
        st.info("Add at least one complete section to see the results.")
        return
    res = pd.DataFrame(rows)
    full_width(st.dataframe, res, hide_index=True)

    tdh = res["Total head (m)"].sum()
    static = res["Static (m)"].sum()
    fric = res["Friction (m)"].sum() + res["Fittings (m)"].sum()
    kw = 1000 * G * tdh * q / (3600 * eff) / 1000
    a, b, c, d = st.columns(4)
    a.metric("TDH", f"{tdh:.2f} m")
    b.metric("Static lift", f"{static:.2f} m")
    c.metric("Friction + fittings", f"{fric:.2f} m")
    d.metric("Pump power", f"{kw:.2f} kW")
    if (res["Velocity (m/s)"] > 2.0).any():
        st.warning("Some sections exceed 2 m/s. Consider a larger pipe there.")

    with st.expander("Check a pump against its curve"):
        st.caption("Enter two points from the solar pump's performance table (Q = daily output, m³/day).")
        c1, c2, c3, c4 = st.columns(4)
        h1 = c1.number_input("H1 (m)", 0.0, 500.0, 77.0)
        q1 = c2.number_input("Q1 (m³/day)", 0.0, 5000.0, 100.0)
        h2 = c3.number_input("H2 (m)", 0.0, 500.0, 44.0)
        q2 = c4.number_input("Q2 (m³/day)", 0.0, 5000.0, 180.0)
        hours = st.number_input("Pumping hours per day", 1.0, 24.0,
                                float(demand["hours"]) if demand else 7.0, 0.5, key="pm_hours")
        if h1 != h2:
            qx = (tdh - h1) * (q1 - q2) / (h1 - h2) + q1
            qh = qx / hours
            st.write(f"At TDH {tdh:.1f} m the pump gives about **{qx:.0f} m³/day** = **{qh:.2f} m³/h** "
                     f"over {hours:g} h, against a required **{q:.2f} m³/h**.")
            if qh >= q:
                st.success("Pump meets the required flow ✔")
            else:
                st.error("Pump flow is below the required flow ✖")

    with st.expander("Inside-diameter reference (mm)"):
        ref = pd.DataFrame({"OD (mm)": [20, 25, 32, 40, 50, 63, 75, 90, 110],
                            "PN10 ID": [16.0, 21.0, 28.0, 35.2, 44.0, 55.4, 66.0, 79.2, 96.8],
                            "PN16 ID": [16.0, 20.4, 26.2, 32.6, 40.8, 51.4, 61.4, 73.6, 90.0]})
        st.dataframe(ref, hide_index=True)
        st.write("Typical C: HDPE / uPVC 150 · HDPE conservative 140 · medium GI 120 · new steel 140")


# ============================================================ main
TOOLS = {"Pump Sizing": ("Pump Sizing Calculator", pump_sizing),
         "Water Demand": ("Water Demand", water_demand),
         "Pumping Main (TDH)": ("Pumping Main: TDH by sections", pumping_main)}


def main():
    setup_page()
    with st.sidebar:
        st.header("Menu")
        tool = st.radio("Tool", list(TOOLS), label_visibility="collapsed")
    title, fn = TOOLS[tool]
    hero(title)
    fn()


LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAANwAAAEfCAMAAAAdj1gdAAAWfmNhQlgAABZ+anVtYgAAAB5qdW1kYzJwYQARABCAAACqADibcQNjMnBhAAAAFlhqdW1iAAAAR2p1bWRjMm1hABEAEIAAAKoAOJtxA3VybjpjMnBhOmZkYzM0ODFlLWUzMjAtNDQ1Zi04NjEzLTJlMzUzZjdlMTI2MgAAAAOTanVtYgAAAClqdW1kYzJhcwARABCAAACqADibcQNjMnBhLmFzc2VydGlvbnMAAAAAuGp1bWIAAABEanVtZGNib3IAEQAQgAAAqgA4m3ETYzJwYS5pbmdyZWRpZW50LnYzAAAAABhjMnNoenveiT4ega9ytnEmOEcEvQAAAGxjYm9yo2lkYzpmb3JtYXRpaW1hZ2UvcG5namluc3RhbmNlSUR4LHhtcDppaWQ6MDU3ZjhmODYtMjMyMy00OWQ0LWE0MTktOTE5YTI3OTI1YzIxbHJlbGF0aW9uc2hpcGhwYXJlbnRPZgAAAeJqdW1iAAAAQWp1bWRjYm9yABEAEIAAAKoAOJtxE2MycGEuYWN0aW9ucy52MgAAAAAYYzJzaDSeu056JOOknGDT/OpPlzQAAAGZY2JvcqJnYWN0aW9uc4KiZmFjdGlvbmtjMnBhLm9wZW5lZGpwYXJhbWV0ZXJzoWtpbmdyZWRpZW50c4GiY3VybHgtc2VsZiNqdW1iZj1jMnBhLmFzc2VydGlvbnMvYzJwYS5pbmdyZWRpZW50LnYzZGhhc2hYIInK9sj7yQa9ofm77HTFC8oNtHlqRuVXXdmzFxDs0ficpGZhY3Rpb254HWNvbS5hbnRocm9waWMuY2xhdWRlLnByb3ZpZGVkanBhcmFtZXRlcnOheB9jb20uYW50aHJvcGljLm9yaWdpbi1jb25maWRlbmNlZ3Vua25vd25rZGVzY3JpcHRpb254ZkNsYXVkZSBwcm92aWRlZCB0aGlzIGZpbGUgYXQgdGhlIHJlcXVlc3Qgb2YgYSB1c2VyIGFuZCBtYXkgaGF2ZSBjcmVhdGVkIG9yIG1vZGlmaWVkIHRoZSBmaWxlIGNvbnRlbnRzLm1zb2Z0d2FyZUFnZW50oWRuYW1lZkNsYXVkZXJhbGxBY3Rpb25zSW5jbHVkZWT1AAAAyGp1bWIAAABAanVtZGNib3IAEQAQgAAAqgA4m3ETYzJwYS5oYXNoLmRhdGEAAAAAGGMyc2hsUr+3/KgP/sjthULkBceEAAAAgGNib3KlY2FsZ2ZzaGEyNTZjcGFkTQAAAAAAAAAAAAAAAABkaGFzaFggdAsJR7+Fh2UB1hQ6Mjfr+/IOlPenI5t3x0vzQjspIARkbmFtZW5qdW1iZiBtYW5pZmVzdGpleGNsdXNpb25zgaJlc3RhcnQYIWZsZW5ndGgZFooAAAI+anVtYgAAACdqdW1kYzJjbAARABCAAACqADibcQNjMnBhLmNsYWltLnYyAAAAAg9jYm9ypWNhbGdmc2hhMjU2aXNpZ25hdHVyZXhNc2VsZiNqdW1iZj0vYzJwYS91cm46YzJwYTpmZGMzNDgxZS1lMzIwLTQ0NWYtODYxMy0yZTM1M2Y3ZTEyNjIvYzJwYS5zaWduYXR1cmVqaW5zdGFuY2VJRHgseG1wOmlpZDpmMDExODViMi1iMGQ1LTRiYTgtYjc1Mi04ZGI4ZGZhZTIxZDVyY3JlYXRlZF9hc3NlcnRpb25zg6JjdXJseC1zZWxmI2p1bWJmPWMycGEuYXNzZXJ0aW9ucy9jMnBhLmluZ3JlZGllbnQudjNkaGFzaFggicr2yPvJBr2h+bvsdMULyg20eWpG5Vdd2bMXEOzR+JyiY3VybHgqc2VsZiNqdW1iZj1jMnBhLmFzc2VydGlvbnMvYzJwYS5hY3Rpb25zLnYyZGhhc2hYIB2SHsJ1j6y8grEN+hH3GfPffJ7S/8Uuj7cGsUkzpMRIomN1cmx4KXNlbGYjanVtYmY9YzJwYS5hc3NlcnRpb25zL2MycGEuaGFzaC5kYXRhZGhhc2hYIH2wvizFBZDbmznolb/3ujAebNbNMOb6SxXbAezTIT1qdGNsYWltX2dlbmVyYXRvcl9pbmZvo2RuYW1lb0FudGhyb3BpYyBGaWxlc2d2ZXJzaW9uZTEuMC4wa3NwZWNWZXJzaW9uZTIuNC4wAAAQOGp1bWIAAAAoanVtZGMyY3MAEQAQgAAAqgA4m3EDYzJwYS5zaWduYXR1cmUAAAAQCGNib3LShFkCEqIBJhghWQIKMIICBjCCAY2gAwIBAgIUQOWgCu7COdC+uIP6BkIFPWdVEwAwCgYIKoZIzj0EAwMwSTEXMBUGA1UEChMOQW50aHJvcGljLCBQQkMxLjAsBgNVBAMTJUFudGhyb3BpYyBDb250ZW50IENyZWRlbnRpYWxzIFJvb3QgQ0EwHhcNMjYwODA3MTg0MzU2WhcNMjgwODA2MTk0MzU2WjBEMRcwFQYDVQQKEw5BbnRocm9waWMsIFBCQzEpMCcGA1UEAxMgQW50aHJvcGljIENsYXVkZSBDb250ZW50IFNpZ25pbmcwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAASYegpry1AYBRTVNL1CpTlbROnY3dey+UrsF9C3phYrATN3ZHf93Mo8RQN0KOUuOn19P4oWNFWe5n2/She9N7eTo1gwVjAOBgNVHQ8BAf8EBAMCB4AwFQYDVR0lBA4wDAYKKwYBBAGD6F4CATAMBgNVHRMBAf8EAjAAMB8GA1UdIwQYMBaAFM5R4gSBTmRbI/jjxM+aPpzB11zCMAoGCCqGSM49BAMDA2cAMGQCMDFzHRSeAXrSy1WOzkbhPZ6Km2wGTmZ/2gK18k8BQGXyqz88Rdrz6CTX9flAnYNVxgIwcF9c3fVhqmJKpi+UhasNUMko69cyX6STPfta3Q8EjyzDjzoyrol46FP6VFHhvUcJoWNwYWRZDZ4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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"

main()

"""Pumping main by sections -> Total Dynamic Head, pump power, pump curve check."""
from math import pi

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Pumping Main TDH", page_icon="🔧", layout="wide")
st.title("🔧 Pumping Main: TDH by sections")
st.caption("Friction per section: hf = 6.824·L·(V/C)^1.852·D^-1.167 (Hazen-Williams, same as the design sheet).")

# reference inside diameters (mm) = OD - 2 x wall
REF = {"OD (mm)": [20, 25, 32, 40, 50, 63, 75, 90, 110],
       "PN10 / SDR17 ID": [16.0, 21.0, 28.0, 35.2, 44.0, 55.4, 66.0, 79.2, 96.8],
       "PN16 / SDR11 ID": [16.0, 20.4, 26.2, 32.6, 40.8, 51.4, 61.4, 73.6, 90.0]}
C_REF = {"HDPE / uPVC": 150, "HDPE (aged / conservative)": 140, "Medium GI": 120, "New steel": 140}

# ------------------------------------------------------------------ compatibility helpers
def full_width(fn, *args, **kwargs):
    """Call st.dataframe / st.data_editor so it works on old AND new Streamlit versions."""
    try:
        return fn(*args, width="stretch", **kwargs)           # Streamlit >= 1.50
    except (TypeError, st.errors.StreamlitAPIException):
        return fn(*args, use_container_width=True, **kwargs)  # older versions


demand = st.session_state.get("demand")
default_flow = round(demand["flow"], 2) if demand else 23.74

top = st.columns(3)
q = top[0].number_input("Pumping flow (m³/h)", 0.1, 5000.0, default_flow, 0.1,
                        help="Filled from the Water Demand page when available.")
eff = top[1].number_input("Overall pump + motor efficiency", 0.2, 0.95, 0.75, 0.05)
minor = top[2].number_input("Fittings loss (% of friction)", 0.0, 100.0, 10.0)

st.subheader("Sections (edit the table)")
st.caption("Inside diameter (ID, mm) is the true bore. Use the reference table below to pick it. "
           "Extra head = residual pressure, filter loss, etc. Defaults reproduce the design sheet's example.")
base = pd.DataFrame([
    ["1 Riser (pump to ground)", 3.7, 6, 80.0, 150, 0.0],
    ["2 Sump GL to pump house", 7.1, 650, 96.8, 120, 0.0],
    ["3 Pump house to reservoir GL", 3.2, 226, 96.8, 140, 0.0],
    ["4 Tower + tank to inlet", 14.7, 14.7, 80.0, 120, 12.0],
], columns=["Section", "Static lift (m)", "Length (m)", "ID (mm)", "C", "Extra head (m)"])
edited = full_width(st.data_editor, base, num_rows="dynamic", hide_index=True)

rows = []
skipped = 0
for _, r in edited.iterrows():
    try:
        length, d_mm, c = float(r["Length (m)"]), float(r["ID (mm)"]), float(r["C"])
        static_i = float(r["Static lift (m)"]); extra = float(r["Extra head (m)"])
    except (TypeError, ValueError):
        skipped += 1
        continue
    if min(length, d_mm, c) <= 0 or pd.isna(length + d_mm + c + static_i + extra):
        skipped += 1
        continue
    d = d_mm / 1000
    v = (q / 3600) / (pi * d * d / 4)
    hf = length * 6.824 * (v / c) ** 1.852 * d ** -1.167
    fit = hf * minor / 100
    rows.append({"Section": r["Section"], "Velocity (m/s)": round(v, 2), "Friction (m)": round(hf, 2),
                 "Fittings (m)": round(fit, 2), "Static (m)": static_i, "Extra (m)": extra,
                 "Total head (m)": round(hf + fit + static_i + extra, 2)})
if skipped:
    st.warning(f"{skipped} row(s) were ignored because length, ID or C is empty or not above zero.")
if not rows:
    st.info("Add at least one complete section to see the results.")
    st.stop()
res = pd.DataFrame(rows)
full_width(st.dataframe, res, hide_index=True)

tdh = res["Total head (m)"].sum()
static = res["Static (m)"].sum()
fric = res["Friction (m)"].sum() + res["Fittings (m)"].sum()
kw = 1000 * 9.81 * tdh * q / (3600 * eff) / 1000

a, b, c, d = st.columns(4)
a.metric("TDH", f"{tdh:.2f} m")
b.metric("Static lift", f"{static:.2f} m")
c.metric("Friction + fittings", f"{fric:.2f} m")
d.metric("Pump power", f"{kw:.2f} kW")
if (res["Velocity (m/s)"] > 2.0).any():
    st.warning("Some sections exceed 2 m/s. Consider a larger pipe there.")

with st.expander("Check a pump against its curve"):
    st.caption("As in the 'Checking pump Q vs safe yield' sheet: enter two points from the solar pump's "
               "performance table. Its Q values are daily output (m³/day); the check divides by pumping hours.")
    c1, c2, c3, c4 = st.columns(4)
    h1 = c1.number_input("H1 (m)", 0.0, 500.0, 77.0)
    q1 = c2.number_input("Q1 (m³/day)", 0.0, 5000.0, 100.0)
    h2 = c3.number_input("H2 (m)", 0.0, 500.0, 44.0)
    q2 = c4.number_input("Q2 (m³/day)", 0.0, 5000.0, 180.0)
    hours = st.number_input("Pumping hours per day", 1.0, 24.0, demand["hours"] if demand else 7.0, 0.5)
    if h1 != h2:
        qx = (tdh - h1) * (q1 - q2) / (h1 - h2) + q1       # linear interpolation at your TDH
        qh = qx / hours
        st.write(f"At TDH {tdh:.1f} m the pump gives about **{qx:.0f} m³/day** = **{qh:.2f} m³/h** "
                 f"over {hours:g} h, against a required **{q:.2f} m³/h**.")
        if qh >= q:
            st.success("Pump meets the required flow ✔")
        else:
            st.error("Pump flow is below the required flow ✖")

with st.expander("Inside-diameter reference (mm)"):
    st.dataframe(pd.DataFrame(REF), hide_index=True)
    st.write("Typical C values:", C_REF)

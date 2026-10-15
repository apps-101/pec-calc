"""Water demand (irrigation + livestock) -> daily volume and pumping flow."""
import streamlit as st

st.set_page_config(page_title="Water Demand", page_icon="🌱", layout="wide")
st.title("🌱 Water Demand")
st.caption("Follows the irrigation design sheet: ETc → net/gross depth → daily volume → pumping flow.")

# crop: (peak Kc, root zone depth m, allowable depletion p)   Source: design sheet / Allen et al. 1998
CROPS = {"Tomato": (1.15, 1.0, 0.5), "Cabbage": (1.05, 0.5, 0.45), "Carrot": (1.05, 0.6, 0.5),
         "Cauliflower": (1.05, 0.6, 0.5), "Onion": (1.05, 0.6, 0.5), "Garlic": (1.0, 0.6, 0.5),
         "Egg plant": (1.05, 0.6, 0.5), "Peppers": (1.05, 0.8, 0.5), "Cucumber": (1.0, 0.6, 0.5),
         "Water melons": (1.0, 0.4, 0.5), "Beans": (1.15, 0.4, 0.6), "Cotton": (1.2, 1.0, 0.9),
         "Coffee": (1.1, 0.9, 0.5), "Maize": (1.2, 0.9, 0.8), "Millet": (1.0, 1.0, 0.7),
         "Rice": (1.2, 0.5, 0.5), "Banana": (1.2, 0.5, 0.55), "Pumpkin": (1.0, 0.6, 0.5)}
LTU = {"Cattle": 0.7, "Goats": 0.15, "Sheep": 0.15, "Pigs": 0.4, "Poultry": 0.1}  # livestock units per head

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
                         help=f"Table value for {crop}: {zr0} m. The sheet used 0.6 m for tomato.")

with right:
    st.subheader("System")
    area = st.number_input("Command area (ha)", 0.1, 1000.0, 5.0, 0.5)
    eff = st.number_input("Application efficiency", 0.3, 1.0, 0.85, 0.05)
    pr = st.number_input("Sprinkler/rainspray precipitation rate (mm/hr)", 1.0, 100.0, 15.0, 1.0)
    infil = st.number_input("Soil infiltration rate (mm/hr)", 1.0, 100.0, 25.0, 1.0)
    st.subheader("Livestock")
    counts = {a: st.number_input(f"{a} (number)", 0, 100000, v, key=a)
              for a, v in zip(LTU, [200, 100, 50, 50, 0])}
    deficit = st.number_input("Irrigation supplied under deficit irrigation (%)", 10, 100, 50)
    hours = st.number_input("Pumping hours per day", 1.0, 24.0, 7.0, 0.5)

# ---- calculations (same steps as the design sheet) ----
aw = (fc - pwp) * 1000                       # mm of water per m of soil
dnet = aw * p * zr                           # mm
freq = dnet / etc                            # days
fa = st.number_input("Adopted irrigation frequency (days)", 1, 30, 4,
                     help="The design sheet adopts 4 days. Keep it at or below the maximum frequency above.")
dnet_c = fa * etc
dgross = dnet_c / eff
shift = dgross / pr                          # hours per irrigation set
irrigated_ha_day = area / fa
irr_m3 = dgross * 10 * irrigated_ha_day      # m3/day  (1 mm on 1 ha = 10 m3)
live_m3 = sum(n * LTU[a] * 50 for a, n in counts.items()) / 1000   # 1 LTU = 50 L/day
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
if pr > infil:
    st.warning("Precipitation rate exceeds soil infiltration rate: expect runoff. Choose a lower-rate emitter.")
else:
    st.info("Precipitation rate is within the soil infiltration rate. ✔")

st.session_state["demand"] = {"m3_day": deficit_m3, "hours": hours, "flow": flow}
st.caption("Next, open **Pumping Main TDH** in the sidebar; it will pick up this flow automatically.")

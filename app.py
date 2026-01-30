import streamlit as st
import pandas as pd
import math
import os

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------
def calculate_rd_2016(z):
    if z <= 9.15:
        return 1.0 - 0.00765 * z
    elif z <= 23:
        return 1.174 - 0.0267 * z
    elif z <= 30:
        return 0.744 - 0.008 * z
    else:
        return 0.5


def calculate_rd_2025(z, mw):
    # Boulanger & Idriss (2014) rd
    alpha = -1.012 - 1.126 * math.sin(z / 11.73 + 5.133)
    beta = 0.106 + 0.118 * math.sin(z / 11.28 + 5.142)
    return math.exp(alpha + beta * mw)


# --------------------------------------------------
# PAGE SETUP
# --------------------------------------------------
st.set_page_config(page_title="Liquefaction Analysis Comparison", layout="wide")

# --------------------------------------------------
# UI CUSTOMIZATION (CSS)
# --------------------------------------------------
# This CSS hides the "Deploy" button and Footer, but keeps the Main Menu (3 lines).
st.markdown(
    """
    <style>
    /* Hide the 'Deploy' button */
    .stDeployButton {
        visibility: hidden;
    }
    /* Hide the 'Made with Streamlit' footer */
    footer {
        visibility: hidden;
    }
    /* Ensure the Hamburger Menu (3 lines) remains visible */
    #MainMenu {
        visibility: visible;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------------------------
# MAIN TITLE
# --------------------------------------------------
# Creating columns to display image and text side-by-side
col1, col2 = st.columns([1, 6]) # Adjust the ratio as needed

with col1:
    # Ensure the image file is in the same directory as app.py
    # You must save your image as 'icon.png' for this to work
    if os.path.exists("icon.png"):
        st.image("icon.png", width=80)
    else:
        st.write("📊") # Fallback emoji if image is missing

with col2:
    st.title("Liquefaction Analysis: IS 1893 (2016 vs 2025)")

st.markdown("Comparing **IS 1893:2016** with **IS 1893:2025**")

# --------------------------------------------------
# SIDEBAR INPUTS
# --------------------------------------------------
st.sidebar.header("Seismic Parameters")
pga = st.sidebar.number_input("Peak Ground Acceleration (PGA)", value=0.162, format="%.3f")
mw = st.sidebar.number_input("Earthquake Magnitude (Mw)", value=6.50, step=0.1)

st.sidebar.header("Ground Conditions")
gwt = st.sidebar.number_input("Ground Water Table Depth (m)", value=7.00, step=0.1)

st.sidebar.header("Soil Layer Properties")
z = st.sidebar.number_input("Depth of Analysis z (m)", value=7.45, step=0.01)
gamma_sat = st.sidebar.number_input("Saturated Unit Weight γsat (kN/m³)", value=19.00, step=0.01)
n_value = st.sidebar.number_input("Observed SPT N-value", value=14, step=1)
fc = st.sidebar.number_input("Fines Content (%)", value=65.15, step=0.001)

st.sidebar.markdown("---")
st.sidebar.markdown("**Method Specific Inputs**")
fs_exponent = st.sidebar.number_input("2016: Exponent Factor (fs)", value=0.65, step=0.01)
n1_60_assumed = st.sidebar.number_input("2025: Assumed (N1)60 for m [Col AP]", value=37.0, step=1.0,
                                        help="Constant value used in Excel to calculate m")

# --------------------------------------------------
# CALCULATE BUTTON
# --------------------------------------------------
calculate_btn = st.sidebar.button("Calculate", type="primary")

if calculate_btn:
    # --------------------------------------------------
    # COMMON CALCULATIONS (STRESS)
    # --------------------------------------------------
    gamma_w = 9.81
    Pa = 100.0

    sigma_v0 = gamma_sat * z
    if z > gwt:
        sigma_v0_eff = (gamma_sat * gwt) + ((gamma_sat - gamma_w) * (z - gwt))
    else:
        sigma_v0_eff = sigma_v0

    # --------------------------------------------------
    # ANALYSIS 1: IS 1893 - 2016
    # --------------------------------------------------
    # 1. rd
    rd_16 = calculate_rd_2016(z)

    # 2. CSR
    csr_16 = 0.65 * pga * (sigma_v0 / sigma_v0_eff) * rd_16

    # 3. CN
    cn_16 = min(1.7, math.sqrt(Pa / sigma_v0_eff))

    # 4. (N1)60
    n1_60_16 = n_value * cn_16

    # 5. Fines Correction
    if fc <= 5:
        alpha_16, beta_16 = 0.0, 1.0
    elif fc < 35:
        alpha_16 = math.exp(1.76 - (190 / (fc ** 2)))
        beta_16 = 0.99 + (fc ** 1.5 / 1000)
    else:
        alpha_16, beta_16 = 0.5, 1.2

    n1_60cs_16 = alpha_16 + beta_16 * n1_60_16

    # 6. CRR 7.5
    crr_75_16 = (1 / (34 - n1_60cs_16)) + (n1_60cs_16 / 135) + (50 / ((10 * n1_60cs_16 + 45) ** 2)) - (1 / 200)

    # 7. MSF & K_sigma
    msf_16 = (10 ** 2.24) / (mw ** 2.56)
    k_sigma_16 = (sigma_v0_eff / Pa) ** (fs_exponent - 1)

    # 8. Final CRR & FOS
    crr_16 = crr_75_16 * msf_16 * k_sigma_16
    fos_16 = crr_16 / csr_16

    # --------------------------------------------------
    # ANALYSIS 2: IS 1893 - 2025
    # --------------------------------------------------
    # 1. rd (B&I 2014)
    rd_25 = calculate_rd_2025(z, mw)

    # 2. CSR
    csr_25 = 0.65 * pga * (sigma_v0 / sigma_v0_eff) * rd_25

    # 3. Calculate m (Column AQ)
    # Uses the Fixed/Assumed (N1)60 from Column AP (User Input: n1_60_assumed)
    if n1_60_assumed > 0:
        m_25 = 0.784 - 0.0768 * math.sqrt(n1_60_assumed)
    else:
        m_25 = 0.784

    # 4. Calculate CN (Column AR)
    # Formula: (Pa / sigma_v0_eff)^m
    # Note: Excel formula usually doesn't explicitly limit CN here unless specified,
    # but typical practice is <= 1.7. We'll keep the cap to avoid unrealistic values.
    cn_25_raw = (Pa / sigma_v0_eff) ** m_25
    cn_25 = min(1.7, cn_25_raw)

    # 5. Calculate (N1)60 (Column AT)
    # Formula: N * CN
    n1_60_25_calc = n_value * cn_25

    # 6. Calculate Delta(N1)60 (Column AU)
    # Formula: =EXP(1.63+(9.7/(AO4+0.01))-(15.7/(AO4+0.01))^2)
    fc_term = fc + 0.01
    delta_n1_25 = math.exp(1.63 + (9.7 / fc_term) - (15.7 / fc_term) ** 2)

    # 7. Calculate (N1)60cs (Column AV)
    # Formula: = AT4 + AU4 => (N1)60 + Delta(N1)60
    n1_60cs_25 = n1_60_25_calc + delta_n1_25

    # 8. C_sigma (Column AZ)
    # Formula: =1/(18.9-2.55*SQRT(AV4))
    # We add a check to prevent division by zero or sqrt of negative numbers
    if n1_60cs_25 >= 0:
        denom = 18.9 - 2.55 * math.sqrt(n1_60cs_25)
        if abs(denom) < 0.0001:
            c_sigma_25 = 0.0  # Handle singularity
        else:
            c_sigma_25 = 1.0 / denom
    else:
        c_sigma_25 = 0.0

    # 9. K_sigma (Column BA)
    # Formula: =IF(AZ4<0.3, 1-AZ4*LN(K4/P4), 1-0.3*LN(K4/P4))
    # K4 = sigma_v0_eff, P4 = Pa
    if c_sigma_25 < 0.3:
        k_sigma_25 = 1.0 - c_sigma_25 * math.log(sigma_v0_eff / Pa)
    else:
        k_sigma_25 = 1.0 - 0.3 * math.log(sigma_v0_eff / Pa)

    # 10. CRR 7.5 (Column BB)
    # Formula: =EXP(-2.8+(AV4/14.1)+(AV4/126)^2-(AV4/23.6)^3+(AV4/25.4)^4)
    crr_75_25 = math.exp(
        -2.8 +
        (n1_60cs_25 / 14.1) +
        ((n1_60cs_25 / 126) ** 2) -
        ((n1_60cs_25 / 23.6) ** 3) +
        ((n1_60cs_25 / 25.4) ** 4)
    )

    # 11. MSF Calculation
    # MSF Max (Column AW) = 1.09 * ( (N1)60cs / 31.5 )^2
    msf_max_25 = 1.09 * ((n1_60cs_25 / 31.5) ** 2)

    # MSF (Column AY)
    # Formula: = 1 + (AW4 - 1) * (8.64 * EXP(-0.25 * Mw) - 1.325)
    msf_term_B = 8.64 * math.exp(-0.25 * mw) - 1.325
    msf_25 = 1 + (msf_max_25 - 1) * msf_term_B

    # 12. Final CRR (Column BC)
    # Formula: = BB4 * AY4 * BA4 => CRR7.5 * MSF * K_sigma
    crr_25 = crr_75_25 * msf_25 * k_sigma_25

    # 13. FOS
    fos_25 = crr_25 / csr_25

    # --------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("IS 1893 - 2016")

        st.metric("CSR", f"{csr_16:.3f}")
        st.metric("CRR", f"{crr_16:.3f}")

        fos_disp_16 = f"{fos_16:.3f}"
        if fos_16 < 1.0:
            st.error(f"FOS: {fos_disp_16} (Unsafe)")
        elif fos_16 < 1.2:
            st.warning(f"FOS: {fos_disp_16} (Marginal)")
        else:
            st.success(f"FOS: {fos_disp_16} (Safe)")

        with st.expander("Detailed Inputs (2016)"):
            st.write(f"rd: {rd_16:.3f}")
            st.write(f"CN: {cn_16:.3f}")
            st.write(f"(N1)60cs: {n1_60cs_16:.3f}")
            st.write(f"MSF: {msf_16:.3f}")
            st.write(f"Kσ: {k_sigma_16:.3f}")

    with col2:
        st.subheader("IS 1893 - 2025")

        st.metric("CSR", f"{csr_25:.3f}")
        st.metric("CRR", f"{crr_25:.3f}")

        fos_disp_25 = f"{fos_25:.3f}"
        if fos_25 < 1.0:
            st.error(f"FOS: {fos_disp_25} (Unsafe)")
        elif fos_25 < 1.2:
            st.warning(f"FOS: {fos_disp_25} (Marginal)")
        else:
            st.success(f"FOS: {fos_disp_25} (Safe)")

        with st.expander("Detailed Inputs (2025)"):
            st.write(f"rd: {rd_25:.3f}")
            st.write(f"m (using assumed {n1_60_assumed}): {m_25:.3f}")
            st.write(f"CN: {cn_25:.3f}")
            st.write(f"(N1)60 [Calc]: {n1_60_25_calc:.3f}")
            st.write(f"Δ(N1)60: {delta_n1_25:.3f}")
            st.write(f"(N1)60cs: {n1_60cs_25:.3f}")
            st.write(f"Cσ: {c_sigma_25:.3f}")
            st.write(f"Kσ: {k_sigma_25:.3f}")
            st.write(f"MSF Max: {msf_max_25:.3f}")
            st.write(f"MSF: {msf_25:.3f}")

    # --------------------------------------------------
    # COMPARISON TABLE
    # --------------------------------------------------
    st.subheader("📊 Detailed Comparison")

    comp_data = {
        "Parameter": ["rd", "CSR", "(N1)60cs", "MSF", "Kσ", "CRR", "FOS"],
        "IS 1893 - 2016": [rd_16, csr_16, n1_60cs_16, msf_16, k_sigma_16, crr_16, fos_16],
        "IS 1893 - 2025": [rd_25, csr_25, n1_60cs_25, msf_25, k_sigma_25, crr_25, fos_25]
    }
    df_comp = pd.DataFrame(comp_data)
    # Format decimals
    df_comp["IS 1893 - 2016"] = df_comp["IS 1893 - 2016"].map('{:.3f}'.format)
    df_comp["IS 1893 - 2025"] = df_comp["IS 1893 - 2025"].map('{:.3f}'.format)

    st.table(df_comp)

else:
    st.info("👈 Enter parameters in the sidebar and click 'Calculate' to see results.")

# --------------------------------------------------
# CREDITS / DISCLAIMER SECTION
# --------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666;">
        <h3>ℹ️ For Educational Use Only</h3>
        <p style="font-size: 1.1em;">
            <strong>Independent verification is mandatory before professional or statutory use.
        </p>
        <p style="font-size: 1.1em;">
            <strong>Created by:</strong> S.Kalyani | S.Tarun | G.Anil, Guided by:</strong> Dr.Chenna Rajaram and Mrs. Vrushali Kamalakar
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

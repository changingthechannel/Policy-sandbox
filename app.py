pip install streamlit pandas numpy
streamlit run app.py
import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(page_title="UBI Policy Sandbox", layout="wide")

st.title("UBI + Tax Policy Sandbox (MVP)")
st.write("A tiny simulated economy where you can play with tax and UBI levers.")

# -----------------------------
# 1. Define a toy "economy"
# -----------------------------
# Four income groups with population share and average annual income
INCOME_GROUPS = [
    {"name": "Low",           "pop_share": 0.30, "avg_income": 20000, "mpc": 0.95},
    {"name": "Lower-Middle",  "pop_share": 0.40, "avg_income": 40000, "mpc": 0.85},
    {"name": "Upper-Middle",  "pop_share": 0.20, "avg_income": 80000, "mpc": 0.75},
    {"name": "High",          "pop_share": 0.10, "avg_income": 200000, "mpc": 0.60},
]

TOTAL_POP = 100000  # adults in the "country" for this model

# -----------------------------
# 2. Sidebar controls (your levers)
# -----------------------------
st.sidebar.header("Policy Levers")

vat_rate = st.sidebar.slider("VAT on all consumption (%)", 0.0, 30.0, 10.0, 0.5) / 100
luxury_tax_rate = st.sidebar.slider("Luxury tax on high-end consumption (%)", 0.0, 40.0, 10.0, 0.5) / 100
income_tax_rate = st.sidebar.slider("Flat income tax rate (%)", 0.0, 40.0, 15.0, 0.5) / 100

ubi_monthly = st.sidebar.slider("UBI per recipient (per month)", 0, 2000, 800, 50)

ubi_target = st.sidebar.selectbox(
    "Who receives UBI?",
    ["Everyone", "Bottom 50% income", "Bottom 20% income"]
)

st.sidebar.markdown("---")
st.sidebar.write("Population:", TOTAL_POP, "adults")


# -----------------------------
# 3. Build the population table
# -----------------------------
rows = []
cumulative_pop = 0

for g in INCOME_GROUPS:
    group_pop = int(TOTAL_POP * g["pop_share"])
    cumulative_pop += group_pop

    income = g["avg_income"]
    mpc = g["mpc"]

    # Annual consumption (very simplified: income * MPC)
    consumption = income * mpc

    # Split consumption into basic vs luxury
    # Poor: almost all basic, rich: more luxury
    if g["name"] == "Low":
        basic_share, luxury_share = 0.98, 0.02
    elif g["name"] == "Lower-Middle":
        basic_share, luxury_share = 0.95, 0.05
    elif g["name"] == "Upper-Middle":
        basic_share, luxury_share = 0.90, 0.10
    else:  # High
        basic_share, luxury_share = 0.80, 0.20

    basic_cons = consumption * basic_share
    luxury_cons = consumption * luxury_share

    rows.append({
        "group": g["name"],
        "group_pop": group_pop,
        "avg_income": income,
        "mpc": mpc,
        "basic_cons": basic_cons,
        "luxury_cons": luxury_cons,
    })

df = pd.DataFrame(rows)

# -----------------------------
# 4. Tax calculations
# -----------------------------
# VAT applies to all consumption
df["vat_tax_per_person"] = vat_rate * (df["basic_cons"] + df["luxury_cons"])

# Luxury tax applies only to luxury consumption (we could restrict to rich only, but we already biased luxury to rich)
df["lux_tax_per_person"] = luxury_tax_rate * df["luxury_cons"]

# Income tax is flat on all income (MVP)
df["income_tax_per_person"] = income_tax_rate * df["avg_income"]

# Total tax revenue per group
df["total_tax_per_person"] = df["vat_tax_per_person"] + df["lux_tax_per_person"] + df["income_tax_per_person"]
df["total_tax_group"] = df["total_tax_per_person"] * df["group_pop"]

total_tax_revenue = df["total_tax_group"].sum()

# -----------------------------
# 5. UBI allocation
# -----------------------------
# Determine who qualifies for UBI
df = df.sort_values("avg_income").reset_index(drop=True)
df["cum_pop"] = df["group_pop"].cumsum()
df["cum_pop_share"] = df["cum_pop"] / TOTAL_POP

if ubi_target == "Everyone":
    df["ubi_eligible"] = True
elif ubi_target == "Bottom 50% income":
    df["ubi_eligible"] = df["cum_pop_share"] <= 0.50
elif ubi_target == "Bottom 20% income":
    df["ubi_eligible"] = df["cum_pop_share"] <= 0.20

ubi_recipients = int(df.loc[df["ubi_eligible"], "group_pop"].sum())
ubi_annual_per_person = ubi_monthly * 12

total_ubi_cost = ubi_recipients * ubi_annual_per_person

budget_surplus = total_tax_revenue - total_ubi_cost

# -----------------------------
# 6. Disposable income and inequality
# -----------------------------
df["ubi_per_person"] = np.where(df["ubi_eligible"], ubi_annual_per_person, 0.0)

df["disposable_income_per_person"] = (
    df["avg_income"]
    - df["income_tax_per_person"]
    - df["vat_tax_per_person"]
    - df["lux_tax_per_person"]
    + df["ubi_per_person"]
)

# Simple inequality proxy: ratio of top group disposable to bottom group disposable
low_disp = df.iloc[0]["disposable_income_per_person"]
high_disp = df.iloc[-1]["disposable_income_per_person"]
inequality_ratio = high_disp / low_disp if low_disp > 0 else np.nan

# -----------------------------
# 7. Display results
# -----------------------------

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Tax Revenue (annual)", f"${total_tax_revenue:,.0f}")
col2.metric("Total UBI Cost (annual)", f"${total_ubi_cost:,.0f}")
col3.metric("Budget Surplus / Deficit", f"${budget_surplus:,.0f}",
            delta=f"{(budget_surplus / total_tax_revenue * 100):.1f}%" if total_tax_revenue > 0 else None)
col4.metric("Inequality (Top/Bottom disposable)", f"{inequality_ratio:.2f}")

st.markdown("### Group-Level Outcomes")

display_df = df[[
    "group", "group_pop", "avg_income",
    "disposable_income_per_person", "ubi_per_person",
    "total_tax_per_person"
]].copy()

display_df.rename(columns={
    "group": "Income Group",
    "group_pop": "Population",
    "avg_income": "Avg Income (pre-tax)",
    "disposable_income_per_person": "Disposable Income (post-tax+UBI)",
    "ubi_per_person": "UBI Received (annual)",
    "total_tax_per_person": "Taxes Paid (annual)"
}, inplace=True)

st.dataframe(display_df.style.format({
    "Avg Income (pre-tax)": "${:,.0f}",
    "Disposable Income (post-tax+UBI)": "${:,.0f}",
    "UBI Received (annual)": "${:,.0f}",
    "Taxes Paid (annual)": "${:,.0f}",
    "Population": "{:,.0f}",
}))

st.markdown("### Disposable Income by Group")
st.bar_chart(display_df.set_index("Income Group")["Disposable Income (post-tax+UBI)"])

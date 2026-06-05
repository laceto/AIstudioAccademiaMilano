import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Real Estate ROI", layout="wide", page_icon="🏠")

st.title("🏠 Real Estate Investment Dashboard")
st.caption("Simulate your investment return before you buy.")

# ── Sidebar inputs ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Property")
    purchase_price = st.number_input("Purchase Price (€)", 10_000, 5_000_000, 300_000, 5_000)
    notary_pct = st.slider("Notary & Taxes (%)", 0.0, 10.0, 3.0, 0.5,
                           help="Purchase costs on top of price (Italy: ~3-5%)")
    down_payment_pct = st.slider("Down Payment (%)", 5, 100, 20)

    st.header("Mortgage")
    mortgage_rate = st.slider("Rate (%)", 0.5, 10.0, 3.5, 0.1)
    loan_term = st.selectbox("Term (years)", [10, 15, 20, 25, 30], index=3)

    st.header("Rental Income")
    monthly_rent = st.number_input("Monthly Rent (€)", 0, 20_000, 1_200, 50)
    vacancy_rate = st.slider("Vacancy (%)", 0, 30, 5)

    st.header("Annual Expenses")
    property_tax = st.number_input("Property Tax / IMU (€/yr)", 0, 20_000, 800, 100)
    maintenance = st.number_input("Maintenance (€/yr)", 0, 20_000, 1_200, 100)
    insurance = st.number_input("Insurance (€/yr)", 0, 5_000, 400, 50)
    mgmt_fee_pct = st.slider("Mgmt Fee (% of rent)", 0, 20, 0,
                              help="Property manager fee if you outsource")

    st.header("Growth")
    appreciation = st.slider("Annual Appreciation (%)", 0.0, 8.0, 2.0, 0.5)
    rent_growth = st.slider("Annual Rent Growth (%)", 0.0, 6.0, 1.5, 0.5)

# ── Core calculations ────────────────────────────────────────────────────────
notary_cost = purchase_price * notary_pct / 100
down_payment = purchase_price * down_payment_pct / 100
total_upfront = down_payment + notary_cost
loan_amount = purchase_price - down_payment

monthly_rate = mortgage_rate / 100 / 12
n = loan_term * 12
if monthly_rate > 0:
    monthly_mortgage = loan_amount * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
else:
    monthly_mortgage = loan_amount / n

effective_rent = monthly_rent * (1 - vacancy_rate / 100)
mgmt_fee_monthly = effective_rent * mgmt_fee_pct / 100
annual_opex = property_tax + maintenance + insurance + mgmt_fee_monthly * 12
monthly_opex = annual_opex / 12

monthly_cf = effective_rent - monthly_mortgage - monthly_opex
annual_cf = monthly_cf * 12

annual_gross_rent = effective_rent * 12
noi = annual_gross_rent - annual_opex
cap_rate = noi / purchase_price * 100
gross_yield = monthly_rent * 12 / purchase_price * 100
net_yield = noi / purchase_price * 100
cash_on_cash = annual_cf / total_upfront * 100 if total_upfront > 0 else 0

# ── Metrics row ──────────────────────────────────────────────────────────────
st.subheader("Key Metrics")
c1, c2, c3, c4, c5, c6 = st.columns(6)
cf_color = "normal" if monthly_cf >= 0 else "inverse"
c1.metric("Monthly Cash Flow", f"€{monthly_cf:,.0f}")
c2.metric("Cash-on-Cash", f"{cash_on_cash:.1f}%")
c3.metric("Cap Rate", f"{cap_rate:.1f}%")
c4.metric("Gross Yield", f"{gross_yield:.1f}%")
c5.metric("Net Yield", f"{net_yield:.1f}%")
c6.metric("Total Upfront", f"€{total_upfront:,.0f}")

st.divider()

# ── 10-year projection ───────────────────────────────────────────────────────
years = list(range(0, 11))
prop_values, loan_balances, equities, cum_cf, annual_returns = [], [], [], [], []

balance = loan_amount
cum = 0.0
for y in years:
    pv = purchase_price * (1 + appreciation / 100) ** y
    prop_values.append(pv)
    loan_balances.append(max(balance, 0))
    equities.append(pv - max(balance, 0))

    if y > 0:
        yr_rent = monthly_rent * (1 + rent_growth / 100) ** (y - 1) * 12 * (1 - vacancy_rate / 100)
        yr_opex = annual_opex * (1 + 0.02) ** (y - 1)
        yr_noi = yr_rent - yr_opex
        yr_cf = yr_noi - monthly_mortgage * 12
        cum += yr_cf
        # Pay down loan
        for _ in range(12):
            interest = balance * monthly_rate
            principal = monthly_mortgage - interest
            balance = max(balance - principal, 0)
        annual_returns.append(yr_cf)
    else:
        annual_returns.append(0)
    cum_cf.append(cum)

df = pd.DataFrame({
    "Year": years,
    "Property Value (€)": prop_values,
    "Loan Balance (€)": loan_balances,
    "Equity (€)": equities,
    "Cumulative Cash Flow (€)": cum_cf,
})

fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=("Equity Build-up", "Cumulative Cash Flow"),
    horizontal_spacing=0.08,
)

fig.add_trace(go.Scatter(x=years, y=prop_values, name="Property Value",
                          fill="tozeroy", line=dict(color="#4CAF50", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=years, y=equities, name="Equity",
                          fill="tozeroy", line=dict(color="#2196F3", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=years, y=loan_balances, name="Loan Balance",
                          line=dict(color="#F44336", width=2, dash="dash")), row=1, col=1)

bar_colors = ["#4CAF50" if v >= 0 else "#F44336" for v in cum_cf]
fig.add_trace(go.Bar(x=years, y=cum_cf, name="Cum. Cash Flow",
                      marker_color=bar_colors, showlegend=False), row=1, col=2)
fig.add_hline(y=0, line_dash="dot", line_color="gray", row=1, col=2)

fig.update_layout(height=400, template="plotly_white", legend=dict(orientation="h", y=1.12))
fig.update_xaxes(title_text="Year")
fig.update_yaxes(tickprefix="€", tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)

# ── 10-year table ────────────────────────────────────────────────────────────
with st.expander("Year-by-year table"):
    st.dataframe(
        df.set_index("Year").style.format("€{:,.0f}"),
        use_container_width=True,
    )

# ── Sensitivity ──────────────────────────────────────────────────────────────
st.subheader("Sensitivity: Cash-on-Cash vs Rent & Rate")

rents = [monthly_rent * f for f in [0.8, 0.9, 1.0, 1.1, 1.2]]
rates = [mortgage_rate + d for d in [-1.0, -0.5, 0.0, 0.5, 1.0]]

rows = []
for r in rents:
    row = {}
    for mr in rates:
        mr_monthly = mr / 100 / 12
        if mr_monthly > 0:
            mtg = loan_amount * (mr_monthly * (1 + mr_monthly) ** n) / ((1 + mr_monthly) ** n - 1)
        else:
            mtg = loan_amount / n
        eff = r * (1 - vacancy_rate / 100)
        cf_yr = (eff - mtg - monthly_opex) * 12
        coc = cf_yr / total_upfront * 100 if total_upfront > 0 else 0
        row[f"{mr:.1f}%"] = f"{coc:.1f}%"
    rows.append(row)

sens_df = pd.DataFrame(rows, index=[f"€{int(r):,}/mo" for r in rents])
sens_df.index.name = "Rent \\ Rate"
st.dataframe(sens_df, use_container_width=True)
st.caption("Rows = monthly rent scenarios · Columns = mortgage rate scenarios · Values = cash-on-cash return")

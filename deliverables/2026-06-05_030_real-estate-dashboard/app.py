import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from templates.finance.real_estate import (
    compute_roi_metrics,
    project_10yr,
    sensitivity_grid,
)

st.set_page_config(page_title="Real Estate ROI", layout="wide", page_icon="🏠")

st.title("🏠 Real Estate Investment Dashboard")
st.caption("Simulate your investment return before you buy.")

st.warning(
    "**Disclaimer:** This tool provides indicative estimates only and does not constitute "
    "financial or tax advice. Yields shown are before or after cedolare secca as labelled. "
    "Capital gains tax on disposal, tenant default risk, and illiquidity premium are not modelled. "
    "Consult a commercialista before any investment decision.",
    icon="⚠️",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Property")
    purchase_price = st.number_input("Purchase Price (€)", 10_000, 5_000_000, 300_000, 5_000)
    renovation = st.number_input("Renovation Budget (€)", 0, 500_000, 0, 1_000)

    st.header("Purchase Costs")
    notary_pct = st.slider("Notary & Taxes (%)", 0.0, 10.0, 3.0, 0.5,
                           help="Italy: ~3% first home, ~9% second home (imposta di registro)")
    agent_commission_pct = st.slider("Buyer Agent Commission (%)", 0.0, 5.0, 3.0, 0.5,
                                     help="Typical Italian agency fee: 2-3% + VAT")

    st.header("Mortgage")
    down_payment_pct = st.slider("Down Payment (%)", 5, 100, 20)
    mortgage_rate = st.slider("Rate (%)", 0.5, 10.0, 3.5, 0.1)
    loan_term = st.selectbox("Term (years)", [10, 15, 20, 25, 30], index=3)

    st.header("Rental Income")
    monthly_rent = st.number_input("Monthly Rent (€)", 0, 20_000, 1_200, 50)
    vacancy_rate = st.slider("Vacancy (%)", 0, 30, 5)

    st.header("Annual Expenses")
    property_tax = st.number_input("Property Tax / IMU (€/yr)", 0, 20_000, 800, 100)
    maintenance = st.number_input("Maintenance (€/yr)", 0, 20_000, 1_200, 100)
    insurance = st.number_input("Insurance (€/yr)", 0, 5_000, 400, 50)
    mgmt_fee_pct = st.slider("Mgmt Fee (% of rent)", 0, 20, 0)

    st.header("Italian Tax")
    rental_tax_rate = st.slider(
        "Cedolare Secca / IRPEF (%)", 0, 43, 21,
        help="Cedolare secca: 21% long-term, 26% short-term. IRPEF: up to 43%."
    )

    st.header("Growth")
    appreciation = st.slider("Annual Appreciation (%)", -5.0, 8.0, 2.0, 0.5)
    rent_growth = st.slider("Annual Rent Growth (%)", 0.0, 6.0, 1.5, 0.5)
    opex_inflation = st.slider("Opex Inflation (%/yr)", 0.0, 5.0, 2.0, 0.5)

# ── Compute ───────────────────────────────────────────────────────────────────
m = compute_roi_metrics(
    purchase_price=purchase_price,
    notary_pct=notary_pct,
    down_payment_pct=down_payment_pct,
    mortgage_rate_pct=mortgage_rate,
    loan_term_years=loan_term,
    monthly_rent=monthly_rent,
    vacancy_pct=vacancy_rate,
    annual_property_tax=property_tax,
    annual_maintenance=maintenance,
    annual_insurance=insurance,
    mgmt_fee_pct=mgmt_fee_pct,
    rental_tax_rate_pct=rental_tax_rate,
    agent_commission_pct=agent_commission_pct,
    renovation=renovation,
)

# ── Warnings ──────────────────────────────────────────────────────────────────
ltv = m.loan_amount / purchase_price * 100 if purchase_price > 0 else 0
if ltv > 80:
    st.error(f"LTV {ltv:.0f}% — most Italian banks cap at 80% for non-primary residence.")
if m.monthly_cf_aftertax < -300:
    st.warning(f"Monthly cash flow after tax is **€{m.monthly_cf_aftertax:,.0f}**. "
               "This deal requires ongoing capital injection.")

# ── Metrics ───────────────────────────────────────────────────────────────────
st.subheader("Key Metrics")
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Monthly CF (after tax)", f"€{m.monthly_cf_aftertax:,.0f}")
c2.metric("Cash-on-Cash", f"{m.cash_on_cash:.1f}%", help="After cedolare secca / IRPEF")
c3.metric("Cap Rate", f"{m.cap_rate:.1f}%", help="NOI / purchase price — pre-tax, conventional")
c4.metric("Gross Yield", f"{m.gross_yield:.1f}%")
c5.metric("Net Yield (pre-tax)", f"{m.net_yield_pretax:.1f}%")
c6.metric("Net Yield (after tax)", f"{m.net_yield_aftertax:.1f}%")
c7.metric("Total Upfront", f"€{m.total_upfront:,.0f}")

with st.expander("Upfront cost breakdown"):
    st.table(pd.DataFrame({
        "Item": ["Down Payment", "Notary & Taxes", "Buyer Agent", "Renovation"],
        "Amount (€)": [
            f"€{m.down_payment:,.0f}",
            f"€{m.notary_cost:,.0f}",
            f"€{m.agent_cost:,.0f}",
            f"€{m.renovation:,.0f}",
        ],
    }).set_index("Item"))

st.divider()

# ── 10-year projection ────────────────────────────────────────────────────────
df = project_10yr(
    purchase_price=purchase_price,
    loan_amount=m.loan_amount,
    mortgage_rate_pct=mortgage_rate,
    monthly_mortgage=m.monthly_mortgage,
    annual_opex=m.monthly_opex * 12,
    monthly_rent=monthly_rent,
    vacancy_pct=vacancy_rate,
    appreciation_pct=appreciation,
    rent_growth_pct=rent_growth,
    opex_inflation_pct=opex_inflation,
    rental_tax_rate_pct=rental_tax_rate,
)

years = df["Year"].tolist()
fig = make_subplots(
    rows=1, cols=2,
    subplot_titles=("Equity Build-up", "Cumulative Cash Flow (after tax)"),
    horizontal_spacing=0.08,
)
fig.add_trace(go.Scatter(x=years, y=df["Property Value (€)"].tolist(),
                          name="Property Value", fill="tozeroy",
                          line=dict(color="#4CAF50", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=years, y=df["Equity (€)"].tolist(),
                          name="Equity", fill="tozeroy",
                          line=dict(color="#2196F3", width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=years, y=df["Loan Balance (€)"].tolist(),
                          name="Loan Balance",
                          line=dict(color="#F44336", width=2, dash="dash")), row=1, col=1)

cum_vals = df["Cumulative CF (€)"].tolist()
bar_colors = ["#4CAF50" if v >= 0 else "#F44336" for v in cum_vals]
fig.add_trace(go.Bar(x=years, y=cum_vals, name="Cum. CF",
                      marker_color=bar_colors, showlegend=False), row=1, col=2)
fig.add_hline(y=0, line_dash="dot", line_color="gray", row=1, col=2)

fig.update_layout(height=400, template="plotly_white",
                  legend=dict(orientation="h", y=1.12))
fig.update_xaxes(title_text="Year")
fig.update_yaxes(tickprefix="€", tickformat=",.0f")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Year-by-year table"):
    st.dataframe(
        df.set_index("Year").style.format("€{:,.0f}"),
        use_container_width=True,
    )

# ── Sensitivity grid ──────────────────────────────────────────────────────────
st.subheader("Sensitivity: Cash-on-Cash vs Rent & Mortgage Rate")
sens = sensitivity_grid(
    purchase_price=purchase_price,
    loan_amount=m.loan_amount,
    loan_term_years=loan_term,
    total_upfront=m.total_upfront,
    monthly_rent=monthly_rent,
    vacancy_pct=vacancy_rate,
    annual_opex=m.monthly_opex * 12,
    base_mortgage_rate=mortgage_rate,
    rental_tax_rate_pct=rental_tax_rate,
)
st.dataframe(sens, use_container_width=True)
st.caption("Rows = monthly rent scenarios · Columns = mortgage rate scenarios · "
           "Values = after-tax cash-on-cash return · N/A = invalid rate")

# ── CSV export ────────────────────────────────────────────────────────────────
st.divider()
csv = df.to_csv(index=False)
st.download_button(
    label="Export 10-year projection (CSV)",
    data=csv,
    file_name="real_estate_projection.csv",
    mime="text/csv",
)

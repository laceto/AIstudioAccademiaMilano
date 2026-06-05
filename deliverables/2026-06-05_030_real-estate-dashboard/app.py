import sys
from pathlib import Path
# Resolve repo root so imports work regardless of working directory at deploy time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import os
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from templates.finance.real_estate import (
    compute_roi_metrics,
    project_10yr,
    sensitivity_grid,
)
from scripts.market_data import (
    get_omi_benchmark,
    list_cities,
    geocode_city,
    search_idealista,
    summarise_listings,
    FASCIA_LABELS,
)

st.set_page_config(page_title="Real Estate ROI", layout="wide", page_icon="🏠")
st.title("🏠 Real Estate Investment Dashboard")

# ── Sidebar (hoisted above tabs — global singleton, must not be tab-scoped) ──
with st.sidebar:
    st.header("Property")
    purchase_price = st.number_input("Purchase Price (€)", 10_000, 5_000_000, 300_000, 5_000)
    sqm = st.number_input("Size (sqm)", 10, 1_000, 80, 5)
    renovation = st.number_input("Renovation Budget (€)", 0, 500_000, 0, 1_000)

    st.header("Purchase Costs")
    notary_pct = st.slider("Notary & Taxes (%)", 0.0, 10.0, 3.0, 0.5,
                           help="Italy: ~3% first home, ~9% second home")
    agent_commission_pct = st.slider("Buyer Agent Commission (%)", 0.0, 5.0, 3.0, 0.5)

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
        help="Cedolare secca: 21% long-term, 26% short-term. IRPEF: up to 43%.",
    )

    st.header("Growth")
    appreciation = st.slider("Annual Appreciation (%)", -5.0, 8.0, 2.0, 0.5)
    rent_growth = st.slider("Annual Rent Growth (%)", 0.0, 6.0, 1.5, 0.5)
    opex_inflation = st.slider("Opex Inflation (%/yr)", 0.0, 5.0, 2.0, 0.5)

tab_sim, tab_market = st.tabs(["📊 Simulation", "🗺️ Market Data"])

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1 — SIMULATION
# ═══════════════════════════════════════════════════════════════════════════
with tab_sim:
    st.caption("Simulate your investment return before you buy.")
    st.warning(
        "**Disclaimer:** Indicative estimates only — not financial or tax advice. "
        "Capital gains tax on disposal, tenant default risk, and illiquidity premium "
        "are not modelled. Consult a commercialista before investing.",
        icon="⚠️",
    )

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

    price_per_sqm = purchase_price / sqm if sqm > 0 else 0

    ltv = m.loan_amount / purchase_price * 100 if purchase_price > 0 else 0
    if ltv > 80:
        st.error(f"LTV {ltv:.0f}% — most Italian banks cap at 80% for non-primary residence.")
    if m.monthly_cf_aftertax < -300:
        st.warning(
            f"Monthly cash flow after tax is **€{m.monthly_cf_aftertax:,.0f}**. "
            "This deal requires ongoing capital injection."
        )

    st.subheader("Key Metrics")
    c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
    c1.metric("Monthly CF (after tax)", f"€{m.monthly_cf_aftertax:,.0f}")
    c2.metric("Cash-on-Cash", f"{m.cash_on_cash:.1f}%", help="After cedolare secca / IRPEF")
    c3.metric("Cap Rate", f"{m.cap_rate:.1f}%")
    c4.metric("Gross Yield", f"{m.gross_yield:.1f}%")
    c5.metric("Net Yield (pre-tax)", f"{m.net_yield_pretax:.1f}%")
    c6.metric("Net Yield (after tax)", f"{m.net_yield_aftertax:.1f}%")
    c7.metric("Price / sqm", f"€{price_per_sqm:,.0f}")
    c8.metric("Total Upfront", f"€{m.total_upfront:,.0f}")

    with st.expander("Upfront cost breakdown"):
        st.table(pd.DataFrame({
            "Item": ["Down Payment", "Notary & Taxes", "Buyer Agent", "Renovation"],
            "Amount": [
                f"€{m.down_payment:,.0f}", f"€{m.notary_cost:,.0f}",
                f"€{m.agent_cost:,.0f}", f"€{m.renovation:,.0f}",
            ],
        }).set_index("Item"))

    st.divider()

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
    fig.add_trace(go.Bar(x=years, y=cum_vals,
                          marker_color=["#4CAF50" if v >= 0 else "#F44336" for v in cum_vals],
                          showlegend=False), row=1, col=2)
    fig.add_hline(y=0, line_dash="dot", line_color="gray", row=1, col=2)
    fig.update_layout(height=400, template="plotly_white", legend=dict(orientation="h", y=1.12))
    fig.update_xaxes(title_text="Year")
    fig.update_yaxes(tickprefix="€", tickformat=",.0f")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Year-by-year table"):
        st.dataframe(df.set_index("Year").style.format("€{:,.0f}"), use_container_width=True)

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
    st.caption("Rows = rent scenarios · Columns = mortgage rate scenarios · N/A = invalid rate")

    st.divider()
    st.download_button(
        "Export 10-year projection (CSV)",
        df.to_csv(index=False),
        "real_estate_projection.csv",
        "text/csv",
    )


# ═══════════════════════════════════════════════════════════════════════════
# TAB 2 — MARKET DATA
# ═══════════════════════════════════════════════════════════════════════════
with tab_market:
    st.subheader("Market Benchmarks")
    st.warning(
        "**OMI data is from H2 2024** (Agenzia delle Entrate, H1 and H2 2025 editions now "
        "available). Values are official fiscal ranges for *abitazioni civili (A), stato normale "
        "(N)* — they are NOT current market prices and must NOT be used as the sole basis for "
        "any investment decision. Achievable rents in high-demand areas can exceed OMI maxima "
        "by 30–70%. Always verify against live listings.",
        icon="⚠️",
    )
    st.caption(
        "Source: Osservatorio del Mercato Immobiliare — "
        "[agenziaentrate.gov.it](https://www.agenziaentrate.gov.it/portale/schede/"
        "fabbricatiterreni/omi/banche-dati/quotazioni-immobiliari)"
    )

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        city = st.selectbox("City", list_cities(), index=list_cities().index("Milano"))
    with col_b:
        fascia = st.selectbox("Zone", list(FASCIA_LABELS.keys()),
                              format_func=lambda k: FASCIA_LABELS[k], index=1)
    with col_c:
        prop_sqm = st.number_input("Property size (sqm)", 10, 500, sqm, 5, key="mkt_sqm")

    bench = get_omi_benchmark(city, fascia)
    if bench:
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Sale price min (€/sqm)", f"€{bench['sale_min']:,}")
        m2.metric("Sale price max (€/sqm)", f"€{bench['sale_max']:,}")
        m3.metric("Rent min (€/sqm/mo)", f"€{bench['rent_min']:.1f}")
        m4.metric("Rent max (€/sqm/mo)", f"€{bench['rent_max']:.1f}")

        implied_price_mid = bench["sale_mid"] * prop_sqm
        implied_rent_mid = bench["rent_mid"] * prop_sqm

        st.info(
            f"For a **{prop_sqm} sqm** property in **{city} {FASCIA_LABELS[fascia]}**:\n\n"
            f"- Implied purchase price: **€{bench['sale_min'] * prop_sqm:,.0f} – "
            f"€{bench['sale_max'] * prop_sqm:,.0f}** (mid: €{implied_price_mid:,.0f})\n"
            f"- Implied monthly rent: **€{bench['rent_min'] * prop_sqm:,.0f} – "
            f"€{bench['rent_max'] * prop_sqm:,.0f}** (mid: €{implied_rent_mid:,.0f})\n\n"
            f"*Source: {bench['source']}*"
        )

        st.subheader(f"Zone comparison — {city}, {prop_sqm} sqm")
        rows = []
        for fk, fl in FASCIA_LABELS.items():
            b = get_omi_benchmark(city, fk)
            if b:
                rows.append({
                    "Zone": fl,
                    "Sale min (€)": b["sale_min"] * prop_sqm,
                    "Sale max (€)": b["sale_max"] * prop_sqm,
                    "Sale mid (€)": b["sale_mid"] * prop_sqm,
                    "Rent min (€/mo)": round(b["rent_min"] * prop_sqm),
                    "Rent max (€/mo)": round(b["rent_max"] * prop_sqm),
                    "Gross Yield mid (%)": round(
                        b["rent_mid"] * prop_sqm * 12 / (b["sale_mid"] * prop_sqm) * 100, 2
                    ),
                })
        if rows:
            comp_df = pd.DataFrame(rows).set_index("Zone")
            st.dataframe(comp_df.style.format({
                "Sale min (€)": "€{:,.0f}", "Sale max (€)": "€{:,.0f}",
                "Sale mid (€)": "€{:,.0f}", "Rent min (€/mo)": "€{:,.0f}",
                "Rent max (€/mo)": "€{:,.0f}", "Gross Yield mid (%)": "{:.2f}%",
            }), use_container_width=True)
            st.caption("Gross yield = OMI mid rent × 12 / OMI mid sale price — gross, pre-vacancy, pre-tax.")

            fig2 = go.Figure(go.Bar(
                x=[r["Zone"] for r in rows],
                y=[r["Gross Yield mid (%)"] for r in rows],
                marker_color=["#4CAF50", "#2196F3", "#FF9800"],
                text=[f"{r['Gross Yield mid (%)']:.2f}%" for r in rows],
                textposition="outside",
            ))
            fig2.update_layout(
                height=300, template="plotly_white",
                yaxis_title="Gross Yield (%)", xaxis_title="Zone",
                yaxis_range=[0, max(r["Gross Yield mid (%)"] for r in rows) * 1.3],
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Cross-city comparison ─────────────────────────────────────────────
    st.subheader("Gross Yield — All Cities (OMI mid-range, gross pre-tax)")
    city_fascia = st.selectbox(
        "Compare cities by zone",
        list(FASCIA_LABELS.keys()),
        format_func=lambda k: FASCIA_LABELS[k],
        index=1,
        key="city_fascia",
    )
    city_rows = []
    for c in list_cities():
        b = get_omi_benchmark(c, city_fascia)
        if b and b["sale_mid"] > 0:
            gross_yield = b["rent_mid"] * 12 / b["sale_mid"] * 100
            city_rows.append({
                "City": c,
                "Gross Yield (%)": round(gross_yield, 2),
                "Sale mid (€/sqm)": b["sale_mid"],
                "Rent mid (€/sqm/mo)": b["rent_mid"],
            })
    if city_rows:
        city_df = pd.DataFrame(city_rows).sort_values("Gross Yield (%)", ascending=False)
        fig3 = go.Figure(go.Bar(
            x=city_df["City"], y=city_df["Gross Yield (%)"],
            marker_color="#2196F3",
            text=[f"{v:.2f}%" for v in city_df["Gross Yield (%)"]],
            textposition="outside",
        ))
        fig3.update_layout(
            height=360, template="plotly_white",
            yaxis_title="Gross Yield (%)",
            yaxis_range=[0, city_df["Gross Yield (%)"].max() * 1.25],
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.dataframe(city_df.set_index("City").style.format({
            "Gross Yield (%)": "{:.2f}%",
            "Sale mid (€/sqm)": "€{:,}",
            "Rent mid (€/sqm/mo)": "€{:.1f}",
        }), use_container_width=True)

    st.divider()

    # ── Idealista live listings ───────────────────────────────────────────
    st.subheader("Live Listings — Idealista API")
    has_idealista = bool(os.getenv("IDEALISTA_API_KEY") and os.getenv("IDEALISTA_SECRET"))

    if not has_idealista:
        st.info(
            "Set `IDEALISTA_API_KEY` and `IDEALISTA_SECRET` environment variables to enable "
            "live listing search. Apply for a free developer key at **api.idealista.com**."
        )
    else:
        col_i1, col_i2, col_i3 = st.columns([2, 1, 1])
        with col_i1:
            search_city = st.text_input("Search city", city, key="idealista_city")
        with col_i2:
            operation = st.selectbox("Operation", ["sale", "rent"])
        with col_i3:
            radius = st.slider("Radius (km)", 1, 10, 2) * 1000

        if st.button("Search Idealista"):
            with st.spinner("Geocoding…"):
                geo_result = geocode_city(search_city)

            if isinstance(geo_result[0], float):
                lat, lng = geo_result
                with st.spinner(f"Fetching {operation} listings near {search_city}…"):
                    listings = search_idealista(lat, lng, operation, radius)
                if not listings:
                    st.warning("No listings returned. Check your API credentials or try a larger radius.")
                else:
                    summary = summarise_listings(listings)
                    if summary:
                        s1, s2, s3, s4 = st.columns(4)
                        label = "€/sqm" if operation == "sale" else "€/sqm/mo"
                        s1.metric("Listings found", summary["count"])
                        s2.metric(f"Median {label}", f"€{summary['price_per_sqm_median']:,.0f}")
                        s3.metric(f"Min {label}", f"€{summary['price_per_sqm_min']:,.0f}")
                        s4.metric(f"Max {label}", f"€{summary['price_per_sqm_max']:,.0f}")

                    rows_l = []
                    for listing in listings[:20]:
                        size = listing.get("size") or 0
                        price = listing.get("price")
                        rows_l.append({
                            "Price (€)": price,
                            "Size (sqm)": size,
                            "Rooms": listing.get("rooms"),
                            "Floor": listing.get("floor"),
                            "District": listing.get("district"),
                            "€/sqm": round(price / size) if price and size > 0 else None,
                            "Link": listing.get("url", ""),
                        })
                    st.dataframe(pd.DataFrame(rows_l), use_container_width=True)
            else:
                _reason = geo_result[1]
                msgs = {
                    "timeout": "Geocoding timed out. Try again or check your network.",
                    "not_found": f"Could not find '{search_city}'. Try a different spelling or add the province.",
                    "error": "Geocoding failed due to an unexpected error.",
                }
                st.error(msgs.get(_reason, "Geocoding failed."))

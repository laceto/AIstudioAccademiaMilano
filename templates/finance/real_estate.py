from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


def compute_mortgage_payment(loan: float, annual_rate_pct: float, term_years: int) -> float:
    if loan <= 0 or term_years <= 0:
        return 0.0
    if annual_rate_pct <= 0:
        return loan / (term_years * 12)
    r = annual_rate_pct / 100 / 12
    n = term_years * 12
    return loan * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


@dataclass
class ROIMetrics:
    down_payment: float
    notary_cost: float
    agent_cost: float
    renovation: float
    total_upfront: float
    loan_amount: float
    monthly_mortgage: float
    monthly_opex: float
    monthly_cf_pretax: float
    monthly_cf_aftertax: float
    annual_cf_pretax: float
    annual_cf_aftertax: float
    noi: float
    cap_rate: float
    gross_yield: float
    net_yield_pretax: float
    net_yield_aftertax: float
    cash_on_cash: float


def compute_roi_metrics(
    purchase_price: float,
    notary_pct: float,
    down_payment_pct: float,
    mortgage_rate_pct: float,
    loan_term_years: int,
    monthly_rent: float,
    vacancy_pct: float,
    annual_property_tax: float,
    annual_maintenance: float,
    annual_insurance: float,
    mgmt_fee_pct: float,
    rental_tax_rate_pct: float,
    agent_commission_pct: float = 3.0,
    renovation: float = 0.0,
) -> ROIMetrics:
    notary_cost = purchase_price * notary_pct / 100
    agent_cost = purchase_price * agent_commission_pct / 100
    down_payment = purchase_price * down_payment_pct / 100
    total_upfront = down_payment + notary_cost + agent_cost + renovation
    loan_amount = purchase_price - down_payment

    monthly_mortgage = compute_mortgage_payment(loan_amount, mortgage_rate_pct, loan_term_years)

    effective_rent = monthly_rent * (1 - vacancy_pct / 100)
    mgmt_monthly = effective_rent * mgmt_fee_pct / 100
    annual_opex = annual_property_tax + annual_maintenance + annual_insurance + mgmt_monthly * 12
    monthly_opex = annual_opex / 12

    monthly_cf_pretax = effective_rent - monthly_mortgage - monthly_opex
    annual_cf_pretax = monthly_cf_pretax * 12

    annual_gross_rent = effective_rent * 12
    noi = annual_gross_rent - annual_opex
    annual_rental_tax = annual_gross_rent * rental_tax_rate_pct / 100
    annual_cf_aftertax = annual_cf_pretax - annual_rental_tax
    monthly_cf_aftertax = annual_cf_aftertax / 12

    cap_rate = noi / purchase_price * 100 if purchase_price > 0 else 0.0
    gross_yield = monthly_rent * 12 / purchase_price * 100 if purchase_price > 0 else 0.0
    net_yield_pretax = noi / purchase_price * 100 if purchase_price > 0 else 0.0
    net_yield_aftertax = (noi - annual_rental_tax) / purchase_price * 100 if purchase_price > 0 else 0.0
    cash_on_cash = annual_cf_aftertax / total_upfront * 100 if total_upfront > 0 else 0.0

    return ROIMetrics(
        down_payment=down_payment,
        notary_cost=notary_cost,
        agent_cost=agent_cost,
        renovation=renovation,
        total_upfront=total_upfront,
        loan_amount=loan_amount,
        monthly_mortgage=monthly_mortgage,
        monthly_opex=monthly_opex,
        monthly_cf_pretax=monthly_cf_pretax,
        monthly_cf_aftertax=monthly_cf_aftertax,
        annual_cf_pretax=annual_cf_pretax,
        annual_cf_aftertax=annual_cf_aftertax,
        noi=noi,
        cap_rate=cap_rate,
        gross_yield=gross_yield,
        net_yield_pretax=net_yield_pretax,
        net_yield_aftertax=net_yield_aftertax,
        cash_on_cash=cash_on_cash,
    )


def project_10yr(
    purchase_price: float,
    loan_amount: float,
    mortgage_rate_pct: float,
    monthly_mortgage: float,
    annual_opex: float,
    monthly_rent: float,
    vacancy_pct: float,
    appreciation_pct: float,
    rent_growth_pct: float,
    opex_inflation_pct: float,
    rental_tax_rate_pct: float,
) -> pd.DataFrame:
    monthly_rate = mortgage_rate_pct / 100 / 12
    balance = loan_amount
    rows = [
        {
            "Year": 0,
            "Property Value (€)": purchase_price,
            "Loan Balance (€)": balance,
            "Equity (€)": purchase_price - balance,
            "Annual CF After Tax (€)": 0.0,
            "Cumulative CF (€)": 0.0,
        }
    ]

    cum = 0.0
    for y in range(1, 11):
        # Amortise 12 months BEFORE snapshotting — fixes the off-by-one bug
        for _ in range(12):
            interest = balance * monthly_rate
            principal = monthly_mortgage - interest
            balance = max(balance - principal, 0.0)

        pv = purchase_price * (1 + appreciation_pct / 100) ** y
        yr_eff_rent = monthly_rent * (1 + rent_growth_pct / 100) ** (y - 1) * (1 - vacancy_pct / 100) * 12
        yr_opex = annual_opex * (1 + opex_inflation_pct / 100) ** (y - 1)
        yr_rental_tax = yr_eff_rent * rental_tax_rate_pct / 100
        yr_cf = yr_eff_rent - yr_opex - monthly_mortgage * 12 - yr_rental_tax
        cum += yr_cf

        rows.append({
            "Year": y,
            "Property Value (€)": pv,
            "Loan Balance (€)": balance,
            "Equity (€)": pv - balance,
            "Annual CF After Tax (€)": yr_cf,
            "Cumulative CF (€)": cum,
        })

    return pd.DataFrame(rows)


def sensitivity_grid(
    purchase_price: float,
    loan_amount: float,
    loan_term_years: int,
    total_upfront: float,
    monthly_rent: float,
    vacancy_pct: float,
    annual_opex: float,
    base_mortgage_rate: float,
    rental_tax_rate_pct: float = 0.0,
    rent_multipliers: list | None = None,
    rate_deltas: list | None = None,
) -> pd.DataFrame:
    if rent_multipliers is None:
        rent_multipliers = [0.8, 0.9, 1.0, 1.1, 1.2]
    if rate_deltas is None:
        rate_deltas = [-1.0, -0.5, 0.0, 0.5, 1.0]

    monthly_opex = annual_opex / 12
    rows, row_labels = [], []

    for rm in rent_multipliers:
        row = {}
        for rd in rate_deltas:
            rate = base_mortgage_rate + rd
            col = f"{rate:.1f}%"
            if rate <= 0:
                row[col] = "N/A"
            else:
                mtg = compute_mortgage_payment(loan_amount, rate, loan_term_years)
                eff = monthly_rent * rm * (1 - vacancy_pct / 100)
                annual_tax = eff * 12 * rental_tax_rate_pct / 100
                annual_cf = (eff - mtg - monthly_opex) * 12 - annual_tax
                coc = annual_cf / total_upfront * 100 if total_upfront > 0 else 0.0
                row[col] = f"{coc:.1f}%"
        rows.append(row)
        row_labels.append(f"€{int(monthly_rent * rm):,}/mo")

    df = pd.DataFrame(rows, index=row_labels)
    df.index.name = "Rent \\ Rate"
    return df

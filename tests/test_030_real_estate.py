import pytest
from templates.finance.real_estate import (
    compute_mortgage_payment,
    compute_roi_metrics,
    project_10yr,
    sensitivity_grid,
)


def _base_metrics(**overrides):
    kwargs = dict(
        purchase_price=300_000,
        notary_pct=3.0,
        down_payment_pct=20,
        mortgage_rate_pct=3.5,
        loan_term_years=25,
        monthly_rent=1_200,
        vacancy_pct=5,
        annual_property_tax=800,
        annual_maintenance=1_200,
        annual_insurance=400,
        mgmt_fee_pct=0,
        rental_tax_rate_pct=21,
        agent_commission_pct=3.0,
        renovation=0,
    )
    kwargs.update(overrides)
    return compute_roi_metrics(**kwargs)


# 1. Zero down payment + zero notary → total_upfront=0 → cash_on_cash=0, no ZeroDivisionError
def test_zero_total_upfront_no_zero_division():
    m = _base_metrics(down_payment_pct=0, notary_pct=0.0, agent_commission_pct=0.0)
    assert m.total_upfront == 0.0
    assert m.cash_on_cash == 0.0


# 2. Mortgage rate = 0 → monthly payment * n == loan exactly (no floating-point drift beyond 1 cent)
def test_zero_rate_exact_repayment():
    loan = 100_000
    term = 10
    payment = compute_mortgage_payment(loan, 0.0, term)
    assert abs(payment * term * 12 - loan) < 0.01


# 3. Short term + high rate → loan balance never goes negative inside the projection
def test_loan_balance_never_negative():
    loan = 100_000
    rate = 9.0
    term = 10
    monthly_mortgage = compute_mortgage_payment(loan, rate, term)
    df = project_10yr(
        purchase_price=150_000,
        loan_amount=loan,
        mortgage_rate_pct=rate,
        monthly_mortgage=monthly_mortgage,
        annual_opex=0,
        monthly_rent=0,
        vacancy_pct=0,
        appreciation_pct=0.0,
        rent_growth_pct=0.0,
        opex_inflation_pct=0.0,
        rental_tax_rate_pct=0.0,
    )
    assert (df["Loan Balance (€)"] >= 0).all()


# 4. Sensitivity grid with sub-zero rate column → cell shows "N/A", no crash
def test_sensitivity_negative_rate_shows_na():
    grid = sensitivity_grid(
        purchase_price=200_000,
        loan_amount=160_000,
        loan_term_years=25,
        total_upfront=40_000,
        monthly_rent=1_000,
        vacancy_pct=5,
        annual_opex=2_400,
        base_mortgage_rate=0.5,
        rate_deltas=[-1.0, 0.0],
    )
    assert grid["-0.5%"].iloc[0] == "N/A"


# 5. Equity off-by-one fix: year-1 equity must reflect year-1 (post-amortisation) balance
def test_equity_uses_post_amortisation_balance():
    loan = 120_000
    rate = 0.0
    term = 10
    monthly_payment = compute_mortgage_payment(loan, rate, term)
    df = project_10yr(
        purchase_price=200_000,
        loan_amount=loan,
        mortgage_rate_pct=rate,
        monthly_mortgage=monthly_payment,
        annual_opex=0,
        monthly_rent=0,
        vacancy_pct=0,
        appreciation_pct=0.0,
        rent_growth_pct=0.0,
        opex_inflation_pct=0.0,
        rental_tax_rate_pct=0.0,
    )
    expected_balance_yr1 = loan - monthly_payment * 12
    assert df.loc[df["Year"] == 1, "Loan Balance (€)"].iloc[0] == pytest.approx(expected_balance_yr1, abs=0.50)
    expected_equity_yr1 = 200_000 - expected_balance_yr1
    assert df.loc[df["Year"] == 1, "Equity (€)"].iloc[0] == pytest.approx(expected_equity_yr1, abs=0.50)

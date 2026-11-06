---
request_id: "045"
date: "2026-10-16"
intent: bank_statement_analyst
product_type: bank_statement_analyst
outcome: success
price: "14.90"
invoice_id: "—"
agents_invoked:
  - name: Stacy
    role: intent_classifier
    action: >
      "Analista estratto conto banca pdf tutti i trimestri classificazioni voci" -> not in the price list
      (unknown_product). Asked Luigi: tool + analysis of his statements, banks Credem and ING, price 14.90.
      New product key bank_statement_analyst registered in CLAUDE.md, global_settings.json, intent_registry.yaml.
    duration_sec: 0
    status: ok
  - name: Gianni
    role: technical_scoper
    action: >
      No statement PDFs in the repo or on Drive. Stack: pdfplumber (words with positions), column of each amount
      from the Dare/Avere or Uscite/Entrate header, balance reconciliation as the parse check, YAML regex rules
      (no LLM: no cost, no personal data sent out), openpyxl report, CLI. Statements gitignored.
    duration_sec: 0
    status: ok
  - name: Chiara
    role: implementer
    action: >
      Tests first (24, synthetic Credem and ING PDFs made with fpdf2), then bankanalyst/: amounts, profiles, parse,
      classify + rules.yaml (18 categories, overrides, transfers excluded from totals), report (quarters, dedupe
      across overlapping statements, Excel with 5 sheets), cli.
    duration_sec: 0
    status: ok
  - name: Stacy QA
    role: qa_validator
    action: >
      24/24 new tests pass; full suite has 21 collection errors that are identical on main (missing optional
      deps in the container). CLI run end to end on the synthetic statements: quadratura ok on both. Disclaimer
      (not financial or tax advice) in the guide.
    duration_sec: 0
    status: ok
  - name: Marco
    role: finance
    action: "14.90, set by Luigi in the session."
    duration_sec: 0
    status: ok
  - name: Francesca
    role: delivery
    action: "Branch claude/bank-statement-analyst, PR to main."
    duration_sec: 0
    status: ok
skills_used: [pdf_table_extraction, italian_amount_parsing, rule_based_transaction_classification, excel_report_generation]
learning_flags:
  new_skills: [pdf_table_extraction, italian_amount_parsing, rule_based_transaction_classification, excel_report_generation]
  new_mcp: []
  risk_score: 2
  lessons:
    - agent: Chiara
      cue: "When parsing tabular amounts out of a PDF (bank statements, invoices)"
      lesson: "Take the sign from the column position under the header, and check the parse against the document's own totals (opening + movements = closing)."
      evidence: "045: the reconciliation check caught a wrong expected closing balance in the first test run."
      confidence: medium
    - agent: Gianni
      cue: "When building a parser for a document layout nobody has seen (a bank, a supplier, a form)"
      lesson: "Get one real sample before writing the parser, and build the synthetic test fixture from it; a guessed layout costs a second build."
      evidence: "045: the Credem layout guessed from memory (Dare/Avere, one line per movement) matched nothing in the real statements (IMPORTO A DEBITO/CREDITO, description above and below the amount row, row stripes); 0 of 5 reconciled until the parser was rebuilt on a real sample."
      confidence: high
---

# 045 — Analista estratti conto

Real Credem and ING layouts were not available: parser tested only on synthetic PDFs.
Next step: run on Luigi's statements and adapt `bankanalyst/profiles.py` if the reconciliation is not `ok`.

## Follow-up 2026-11-06: real Credem statements

Luigi sent 5 Credem statements (Q4 2024 – Q4 2025). The first run read them as an unknown layout,
nothing reconciled. Rebuilt on the real layout: header IMPORTO A DEBITO / IMPORTO A CREDITO, bank
recognised from the legal footer, each movement a block with description above and below the
dates/amount row, block bounds from the shaded row stripes (gap fallback when a page has none),
Credem margin print code removed, table closed at SALDO FINE PERIODO (conto scalare ignored).
Result: 471 movements, 5/5 reconciled to the cent, Q1 2025 totals equal the bank's own summary.
Rules: compenso misfiled as Salute (`cup ` matched a CUP code), assegno unico as Tasse, COMM. as
Bonifici — fixed, with regression tests; new categories (carta di credito, casa acquisto/notaio,
assegni pubblici, tabacchi, cura personale, regali, svago); investments marked as transfers;
personal rules file layered on the defaults (kept out of the repo: it holds names). 17 movements
(1.467,82 €) left unclassified. 36 offline tests. ING still untested on a real statement.

## Follow-up 2026-11-06: real ING statements

Luigi sent 4 ING Conto Arancio statements (Q4 2024 – Q3 2025). Amounts reconciled on the first
run, but descriptions lost the merchant: ING continues the description below the amount row and
some continuation lines start with a date ("28/09/2024 ALLE ORE…"), which were taken for movements
without an amount. Fix: a line starting in the description column is description, whatever its
first word; the currency word after the amount ("€") is dropped; "CONTO CORRENTE ARANCIO" added to
the ING markers. Rules: coupons/dividends as income (were excluded as transfers), dossier stamp duty
as a cost, `tribut` matched "distributore", `garage` matched a restaurant; ING merchants added
(Amazon, OVS, parking, beach, travel…). Result: 4/4 reconciled; with Credem 9 statements, 1.466
movements, every Credem→ING transfer matched by bank reference. 202 movements (6.388,81 €, of which
2.079,84 € in three MAV) left unclassified. 42 offline tests (the "€" case needs the DejaVu font,
skipped where it is missing).

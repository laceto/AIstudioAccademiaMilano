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
---

# 045 — Analista estratti conto

Real Credem and ING layouts were not available: parser tested only on synthetic PDFs.
Next step: run on Luigi's statements and adapt `bankanalyst/profiles.py` if the reconciliation is not `ok`.

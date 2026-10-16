"""python -m bankanalyst <cartella o PDF…> [--out report.xlsx] [--rules regole.yaml]"""
import argparse
from pathlib import Path

from bankanalyst.amounts import fmt_eur
from bankanalyst.parse import parse_statement
from bankanalyst.report import analyze, write_excel


def _pdfs(inputs: list[str]) -> list[Path]:
    found = []
    for raw in inputs:
        p = Path(raw)
        found += sorted(p.rglob("*.pdf")) + sorted(p.rglob("*.PDF")) if p.is_dir() else [p]
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bankanalyst", description="Estratti conto Credem / ING → movimenti classificati per trimestre")
    ap.add_argument("inputs", nargs="+", help="PDF o cartelle di PDF")
    ap.add_argument("--out", default="analisi_estratti_conto.xlsx")
    ap.add_argument("--rules", help="file YAML di regole (default: bankanalyst/rules.yaml)")
    args = ap.parse_args(argv)

    pdfs = _pdfs(args.inputs)
    if not pdfs:
        print("Nessun PDF trovato.")
        return 1
    statements = [parse_statement(p) for p in pdfs]
    result = analyze(statements, args.rules)
    out = write_excel(result, args.out)

    print(f"{len(pdfs)} estratti conto, {len(result.transactions)} movimenti\n")
    print(f"{'Trimestre':<10} {'Entrate':>14} {'Uscite':>14} {'Netto':>14} {'Giroconti':>12}")
    for q, v in result.totals.items():
        print(f"{q:<10} {fmt_eur(v['entrate']):>14} {fmt_eur(v['uscite']):>14} {fmt_eur(v['netto']):>14} "
              f"{fmt_eur(v['giroconti']):>12}")
    print("\nPer categoria (tutti i trimestri):")
    for cat, by_q in sorted(result.pivot.items(), key=lambda kv: sum(kv[1].values())):
        print(f"  {cat:<30} {fmt_eur(sum(by_q.values())):>14}")
    print(f"\nDa classificare: {len(result.unclassified)}")
    uncertain = sum(t.sign_uncertain for t in result.transactions)
    if uncertain:
        print(f"Segno incerto (layout non riconosciuto): {uncertain}")
    print("\nControlli:")
    for c in result.checks:
        line = f"  {c['file']} [{c['banca']}] {c['movimenti']} movimenti, quadratura saldi: {c['esito']}"
        print(line + (f" — {c['avvisi']}" if c["avvisi"] else ""))
    print(f"\nExcel: {out}")
    return 0

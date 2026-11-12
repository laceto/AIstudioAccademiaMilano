"""python -m bankanalyst <cartella o PDF…> [--out report.xlsx] [--rules regole.yaml]"""
import argparse
from pathlib import Path

from bankanalyst.amounts import fmt_eur
from bankanalyst.parse import parse_statement
from bankanalyst.report import analyze, monthly_budget, split_by_bank, write_excel


def _pdfs(inputs: list[str]) -> list[Path]:
    """Every PDF under the given folders (any case of the extension), each file once.

    rglob("*.pdf") is case-insensitive on Windows: globbing *.pdf and *.PDF there would list every
    statement twice and double all the amounts.
    """
    found: dict[Path, Path] = {}
    for raw in inputs:
        p = Path(raw)
        files = sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() == ".pdf") if p.is_dir() else [p]
        for f in files:
            found.setdefault(f.resolve(), f)
    return list(found.values())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="bankanalyst", description="Estratti conto Credem / ING / Fineco → movimenti classificati per trimestre")
    ap.add_argument("inputs", nargs="+", help="PDF o cartelle di PDF")
    ap.add_argument("--out", default="analisi_estratti_conto.xlsx",
                    help="nome base: scrive un Excel per banca (<nome>_credem.xlsx, <nome>_ing.xlsx, …)")
    ap.add_argument("--combined", action="store_true", help="scrive anche l'Excel unico con tutte le banche (--out)")
    ap.add_argument("--rules", help="file YAML di regole (default: bankanalyst/rules.yaml)")
    ap.add_argument("--llm", action="store_true",
                    help="classifica i 'Da classificare' con OpenAI Batch (kitai); serve OPENAI_API_KEY, invia solo le descrizioni")
    ap.add_argument("--llm-cache", default="llm_categorie.json",
                    help="cache delle categorie LLM (default: llm_categorie.json)")
    args = ap.parse_args(argv)

    pdfs = _pdfs(args.inputs)
    if not pdfs:
        print("Nessun PDF trovato.")
        return 1
    statements = [parse_statement(p) for p in pdfs]
    result = analyze(statements, args.rules)
    if args.llm and result.unclassified:
        from bankanalyst.classify import UNCLASSIFIED, load_rules
        from bankanalyst.llm_classify import classify_with_batch

        try:  # OPENAI_API_KEY lives in the project's .env
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        allowed = {r.name for r in load_rules(args.rules).categories} - {UNCLASSIFIED}
        print(f"LLM batch: {len(result.unclassified)} movimenti da classificare…")
        labels = classify_with_batch(result.unclassified, allowed, cache_path=args.llm_cache)
        result = analyze(statements, args.rules, extra_labels=labels)
    base = Path(args.out)
    outputs = [write_excel(r, base.with_name(f"{base.stem}_{bank}{base.suffix}")) for bank, r in split_by_bank(result).items()]
    if args.combined:
        outputs.insert(0, write_excel(result, base))

    print(f"{len(pdfs)} estratti conto, {len(result.transactions)} movimenti\n")
    print(f"{'Trimestre':<10} {'Entrate':>14} {'Uscite':>14} {'Netto':>14} {'Giroconti':>12} {'Flaggati':>12}")
    for q, v in result.totals.items():
        print(f"{q:<10} {fmt_eur(v['entrate']):>14} {fmt_eur(v['uscite']):>14} {fmt_eur(v['netto']):>14} "
              f"{fmt_eur(v['giroconti']):>12} {fmt_eur(v['flaggati']):>12}")
    print("\nPer categoria (tutti i trimestri):")
    for cat, by_q in sorted(result.pivot.items(), key=lambda kv: sum(kv[1].values())):
        print(f"  {cat:<30} {fmt_eur(sum(by_q.values())):>14}")
    budget = monthly_budget(result)
    if budget.rows:
        print(f"\nBudget: media mensile per categoria, ultimi {budget.months} mesi ({budget.first} - {budget.last}), "
              f"giroconti esclusi")
        print(f"  {'Categoria':<44} {'Mensile':>11} {'Annuo':>13} {'Mesi attivi':>12}")
        for r in budget.rows:
            print(f"  {r.category[:44]:<44} {fmt_eur(r.monthly):>11} {fmt_eur(r.monthly * 12):>13} "
                  f"{r.active_months:>5}/{budget.months}")
        print(f"  {'Entrate':<44} {fmt_eur(budget.income):>11} {fmt_eur(budget.income * 12):>13}")
        print(f"  {'Uscite':<44} {fmt_eur(budget.expenses):>11} {fmt_eur(budget.expenses * 12):>13}")
        net = budget.income + budget.expenses
        print(f"  {'Saldo':<44} {fmt_eur(net):>11} {fmt_eur(net * 12):>13}")
    print(f"\nDa classificare: {len(result.unclassified)}")
    uncertain = sum(t.sign_uncertain for t in result.transactions)
    if uncertain:
        print(f"Segno incerto (layout non riconosciuto): {uncertain}")
    print("\nControlli:")
    for c in result.checks:
        line = f"  {c['file']} [{c['banca']}] {c['movimenti']} movimenti, quadratura saldi: {c['esito']}"
        print(line + (f" — {c['avvisi']}" if c["avvisi"] else ""))
    print("\nExcel:")
    for o in outputs:
        print(f"  {o}")
    return 0

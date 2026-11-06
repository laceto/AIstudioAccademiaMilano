# Estratti conto

Qui vanno i PDF degli estratti conto da analizzare con `bankanalyst` (delivery 045).
**Restano solo sul tuo PC:** git ignora tutto il contenuto della cartella tranne questa guida,
i segnaposto `.gitkeep` e `mie_regole.example.yaml`.

```
estratti_conto/
├── credem/              ← estratti Credem, di qualsiasi anno
├── ing/                 ← estratti ING Conto Arancio
├── mie_regole.yaml      ← le tue regole (copia di mie_regole.example.yaml), mai nel repo
└── analisi.xlsx         ← il risultato, mai nel repo
```

I nomi dei file non contano: banca e periodo si leggono dentro il PDF. Estratti caricati due
volte o sovrapposti non contano doppio.

```bash
pip install -r bankanalyst/requirements.txt
python -m bankanalyst estratti_conto/ --rules estratti_conto/mie_regole.yaml --out estratti_conto/analisi.xlsx
```

Poi apri il foglio **Controlli**: ogni estratto deve avere quadratura `ok`. Un tipo di documento
nuovo (estratto della carta, un'altra banca) va provato prima con un solo PDF.
Guida completa: `deliverables/2026-10-16_045_bank-statement-analyst/README.md`.

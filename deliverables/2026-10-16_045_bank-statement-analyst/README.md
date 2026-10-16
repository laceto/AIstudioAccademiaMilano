# 045 — Analista estratti conto (Credem + ING)

Legge i PDF degli estratti conto, estrae ogni movimento, lo classifica in una categoria e
riassume tutto per trimestre in un file Excel. Prezzo: **14.90**.

## Come si usa

```bash
pip install -r bankanalyst/requirements.txt
# metti i PDF in estratti_conto/ (cartella ignorata da git: i tuoi dati non finiscono nel repo)
python -m bankanalyst estratti_conto/ --out analisi_estratti_conto.xlsx
```

Accetta cartelle (anche con sottocartelle, es. `estratti_conto/credem/`, `estratti_conto/ing/`) e
singoli file. A schermo stampa entrate/uscite/netto per trimestre, i totali per categoria, quanti
movimenti restano da classificare e l'esito della quadratura di ogni estratto.

## Cosa c'è nell'Excel

| Foglio | Contenuto |
|---|---|
| Riepilogo | Per trimestre: entrate, uscite, netto, giroconti, numero movimenti, riga totale |
| Per categoria | Categoria × trimestre, con totale |
| Movimenti | Tutti i movimenti, con filtri: banca, data, valuta, trimestre, descrizione, importo, categoria, file e pagina d'origine |
| Da classificare | Solo quelli che nessuna regola ha riconosciuto |
| Controlli | Per ogni PDF: movimenti letti, saldo iniziale e finale, quadratura, avvisi |

## Come lavora

1. **Lettura.** Le parole del PDF vengono lette con la loro posizione. La riga di intestazione
   della tabella (Dare/Avere per Credem, Uscite/Entrate per ING) dice dove stanno le colonne;
   ogni importo va in uscita o in entrata secondo la colonna sotto cui si trova. Le descrizioni
   su più righe vengono riunite.
2. **Quadratura.** Saldo iniziale + movimenti deve dare il saldo finale. Se non torna, il foglio
   Controlli lo dice con la differenza: vuol dire che qualche riga è stata letta male.
3. **Classificazione.** Regole in `bankanalyst/rules.yaml`, dall'alto in basso, vince la prima.
   I **giroconti tra Credem e ING** hanno una categoria a parte e sono esclusi da entrate e
   uscite, così i soldi che sposti da un conto all'altro non sembrano né spese né guadagni.
4. **Doppioni.** Se due estratti si sovrappongono (es. un mensile e un trimestrale), lo stesso
   movimento viene contato una volta sola. Due movimenti identici nello stesso estratto restano due.

## Correggere le categorie

Copia `bankanalyst/rules.yaml`, modifica e passalo con `--rules mie_regole.yaml`. Il modo più
rapido per sistemare il foglio "Da classificare":

```yaml
overrides:
  'MISTERO SNC': Ristoranti e bar
  'ROSSI MARIO': Affitto e mutuo
```

Un frammento di descrizione → una categoria; gli override vincono su tutte le regole.

## Limiti (da sapere)

- **I layout veri di Credem e ING non li ho ancora visti.** Il parser è stato provato su PDF
  sintetici costruiti come gli estratti di queste due banche (24 test). Al primo giro sui PDF
  reali guarda il foglio Controlli: se la quadratura non è `ok`, mandami il PDF (o anche solo
  una pagina con i dati coperti) e adatto `bankanalyst/profiles.py`.
- **PDF scansionati** (immagini, senza testo) non vengono letti: il foglio Controlli lo segnala.
- Con un layout sconosciuto il segno dell'importo viene dedotto dalle parole ("accredito",
  "stipendio"…) e la colonna "Segno incerto" lo segnala.
- La classificazione è a regole, non usa un modello: niente costi, niente dati inviati fuori,
  ma i commercianti nuovi finiscono in "Da classificare" finché non aggiungi una regola.
- È uno strumento di lettura e riepilogo, non consulenza finanziaria o fiscale.

# SOAP Note Generator

Streamlit app per psicologi: trasforma appunti liberi di seduta in una nota SOAP strutturata (PDF scaricabile).

**Disclaimer: questo strumento genera bozze tramite AI. Ogni output deve essere revisionato e firmato dal clinico responsabile prima di qualsiasi uso clinico o legale.**

## Cosa fa

1. Il clinico incolla le note libere della seduta nell'area di testo.
2. Seleziona (facoltativamente) codice paziente, numero di seduta e approccio terapeutico.
3. Clicca "Genera nota SOAP" — l'app chiama `gpt-4o-mini` e struttura la nota in 4 sezioni:
   - **S — Soggettivo**: cosa ha riportato il paziente
   - **O — Oggettivo**: osservazioni del terapeuta
   - **A — Assessment / Valutazione**: interpretazione clinica
   - **P — Piano**: passi successivi e compiti terapeutici
4. La nota viene mostrata nell'interfaccia e può essere scaricata come PDF firmabile.

## Setup locale

```bash
pip install -r requirements.txt
cp .env.example .env
# modifica .env e inserisci la tua OPENAI_API_KEY
streamlit run app.py
```

## Deploy su Streamlit Cloud

1. Fai push di questa cartella su GitHub.
2. Collega il repo su [share.streamlit.io](https://share.streamlit.io).
3. In **Settings > Secrets** aggiungi:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
4. Imposta `app.py` come file principale.

## Sicurezza e privacy

- Nessun dato viene salvato: la nota risiede solo in `st.session_state` e viene cancellata al ricaricamento della pagina.
- Non inserire mai nomi reali dei pazienti — usare esclusivamente codici anonimi.
- L'API key non viene mai scritta nel codice: usa variabili d'ambiente o Streamlit Secrets.

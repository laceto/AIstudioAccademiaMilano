# Drive Semantic Router (delivery 042)

Smista da solo i file che arrivano nella cartella Google Drive `05_In_Arrivo_Da_Smistare`: estrae il testo,
lo trasforma in un vettore con `all-MiniLM-L6-v2` (in locale, CPU), cerca in ChromaDB la categoria più
vicina e sposta il file nella cartella giusta, rinominandolo `YYYY-MM-DD_Categoria_Descrizione.ext`.

Codice: `driverouter/` · Test: `tests/test_driverouter.py` (27, offline)

| File | Cosa fa |
|------|---------|
| `driverouter/requirements.txt` | Dipendenze, torch CPU-only dall'indice `download.pytorch.org/whl/cpu` |
| `driverouter/classifier.py` | Embeddings + ChromaDB persistente (spazio coseno), categorie con frasi di esempio |
| `driverouter/main.py` | FastAPI (`POST /sync-documents`, `GET /health`), Google Drive, APScheduler, log JSON |
| `driverouter/Dockerfile` | `python:3.11-slim` multi-stage, modello già dentro l'immagine, utente non root |
| `driverouter/deploy_azure.sh` | Resource group, piano F1, Web App container, Key Vault con riferimenti, deploy |

## Come funziona un giro

1. Trova la cartella di arrivo (per percorso o `INBOX_FOLDER_ID`) e legge fino a `MAX_FILES_PER_RUN` file.
2. Testo: Google Docs/Fogli/Presentazioni esportati; PDF con `pypdf`; immagini, PDF scansionati e file
   Word convertiti **da Drive** in un Google Doc temporaneo (OCR in italiano), letti e cancellati subito.
   Niente Tesseract nel container: resta leggero.
3. Il nome del file e i primi ~3000 caratteri diventano al massimo 3 vettori; per ogni categoria conta
   l'esempio più simile.
4. Similarità ≥ `MIN_SIMILARITY` (0.35) → sposta e rinomina. Sotto soglia → il file **resta nella
   cartella di arrivo**, marcato `sr_status=unsure` (nelle `appProperties` di Drive) e non viene più
   riprovato, a meno di `POST /sync-documents?force=true`.
5. Ogni file produce una riga di log JSON (`category`, `similarity`, `runner_up`, `margin`, `method`,
   `duration_ms`): è quella da guardare in Log stream / Application Insights per tarare la soglia.

Categorie di partenza: `Banca`, `Fisco_Tasse`, `Contratti` (in `01_Finanze_Legale/`), `Lavoro` (`02_Lavoro`).
Per cambiarle senza toccare il codice: un JSON `{"Chiave": {"path": "A/B", "examples": ["..."]}}` e
`CATEGORIES_FILE=/percorso/file.json`. L'indice si ricostruisce da solo quando categorie o modello cambiano.

## Sicurezza

- `DRY_RUN=true` di default, anche nello script di deploy: classifica e scrive nei log, **non sposta
  niente**. Mettere `false` solo dopo aver controllato le scelte nei log.
- Segreti solo in Key Vault: l'app li riceve come riferimenti `@Microsoft.KeyVault(...)` tramite la sua
  identità gestita (ruolo *Key Vault Secrets User*, sola lettura). Per Container Apps o in locale,
  `KEY_VAULT_URL` attiva la lettura diretta con `DefaultAzureCredential`.
- `/sync-documents` vuole l'header `X-API-Key` (confronto a tempo costante); senza `SYNC_API_KEY`
  configurata risponde 503, non apre l'accesso. Due sincronizzazioni insieme → 409.
- Scope OAuth: `https://www.googleapis.com/auth/drive` (completo). Serve perché i file nella cartella
  non li ha creati l'app: con `drive.file` non si potrebbero spostare.

## Credenziali Google (una volta sola)

1. Google Cloud Console → abilita **Google Drive API** → schermata consenso → client OAuth tipo *Desktop*.
2. Ottieni un refresh token, sul tuo computer:
   ```
   pip install google-auth-oauthlib
   python -c "from google_auth_oauthlib.flow import InstalledAppFlow as F; c=F.from_client_secrets_file('client_secret.json',['https://www.googleapis.com/auth/drive']).run_local_server(port=0); print(c.refresh_token)"
   ```
   Con l'app in stato *Testing* il refresh token scade dopo 7 giorni: pubblica l'app (anche senza
   verifica, uso personale) per uno che duri.
3. `export GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... GOOGLE_REFRESH_TOKEN=...` — non vanno in `.env`
   committati né nel codice; lo script li copia in Key Vault senza stamparli.

## Deploy

```
docker build -f driverouter/Dockerfile -t ghcr.io/<utente>/drive-router:1 .
docker push ghcr.io/<utente>/drive-router:1          # GHCR: gratis
IMAGE=ghcr.io/<utente>/drive-router:1 REGISTRY_USER=<utente> REGISTRY_PASSWORD=<PAT read:packages> \
  ./driverouter/deploy_azure.sh --dry-run            # anteprima, nessuna modifica
IMAGE=... ./driverouter/deploy_azure.sh
```
Senza `IMAGE` lo script crea un Azure Container Registry **Basic, che non è gratis (~5 €/mese)** e
costruisce l'immagine nel cloud (`az acr build`), utile se non hai Docker in locale.

In locale: `pip install -r driverouter/requirements.txt`, le variabili sopra più `SYNC_API_KEY=...`,
poi `uvicorn driverouter.main:app --port 8000`.

## Limiti del piano Free F1 (da sapere prima)

- **L'app si addormenta** dopo ~20 minuti senza richieste (niente *Always On* su F1): mentre dorme
  APScheduler non gira. Per una scansione regolare serve qualcuno che chiami `/sync-documents`
  dall'esterno, per esempio un workflow GitHub Actions con `schedule:` e il segreto `SYNC_API_KEY`:
  ```yaml
  on: { schedule: [{ cron: "*/30 6-22 * * *" }] }
  jobs: { sync: { runs-on: ubuntu-latest, steps: [{ run: 'curl -fsS -X POST -H "X-API-Key: ${{ secrets.SYNC_API_KEY }}" https://<app>.azurewebsites.net/sync-documents' }] } }
  ```
  La prima chiamata dopo il sonno impiega 1-3 minuti (avvio del container e caricamento del modello).
- **60 minuti di CPU al giorno** e 1 GB di RAM. Caricare il modello costa qualche secondo di CPU a ogni
  risveglio; classificare un file qualche decimo di secondo (stima, non misurata). Per questo `MAX_FILES_PER_RUN=25` e un solo worker.
- L'immagine pesa circa 1,5 GB (torch CPU + modello). Se F1 la rifiuta o va in memoria esaurita,
  l'alternativa è **Azure Container Apps** (consumo, con quota gratuita mensile e scala a zero, e un
  *Container Apps Job* a cron al posto di APScheduler); lo stesso Dockerfile va bene.

## Lingua del modello

`all-MiniLM-L6-v2` è addestrato in inglese: sui documenti italiani funziona, ma meno bene. Ho aggiunto
una frase inglese per categoria e il nome del file nel testo. Se nei log i `margin` restano bassi,
ricostruisci l'immagine con il modello multilingue (più grande, ~470 MB, entra ancora in 1 GB ma stretto):
```
docker build --build-arg EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 ...
```
Cambiando modello cambiano le similarità: ritara `MIN_SIMILARITY` con un giro in `DRY_RUN`.

## Variabili

| Variabile | Default | |
|-----------|---------|--|
| `INBOX_FOLDER_PATH` / `INBOX_FOLDER_ID` | `05_In_Arrivo_Da_Smistare` / — | percorso dalla radice, oppure l'ID diretto |
| `DRIVE_ROOT_FOLDER_ID` | `root` | radice da cui partono i percorsi delle categorie |
| `DRY_RUN` | `true` | non sposta, non rinomina, non marca |
| `RENAME_FILES` | `true` | `YYYY-MM-DD_Categoria_Descrizione.ext` (data di creazione su Drive) |
| `DRIVE_OCR` | `true` | conversione/OCR tramite Drive per immagini, PDF scansionati, Word |
| `CREATE_MISSING_FOLDERS` | `false` | crea le cartelle di destinazione mancanti invece di dare errore |
| `MIN_SIMILARITY` | `0.35` | soglia sotto cui il file resta in arrivo |
| `SYNC_INTERVAL_MINUTES` | `30` | `0` spegne lo scheduler interno |
| `MAX_FILES_PER_RUN`, `MAX_DOWNLOAD_MB` | `25`, `15` | |
| `EMBEDDING_MODEL`, `CATEGORIES_FILE`, `CHROMA_DIR` | MiniLM, categorie interne, `/tmp/chroma` | |
| `KEY_VAULT_URL`, `APPLICATIONINSIGHTS_CONNECTION_STRING` | — | opzionali |

## Stato

Provato: 27 test offline (ChromaDB vero, embedder finto a bag-of-words, Drive finto, API con
TestClient), `bash -n` e `--dry-run` dello script. **Non provato:** il modello vero (Hugging Face e
l'indice PyTorch sono bloccati dalla rete del container in cui è stato scritto), la build Docker, una
cartella Drive reale, il deploy su Azure. La soglia 0.35 è un punto di partenza, non un valore misurato.

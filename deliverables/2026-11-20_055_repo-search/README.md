# 055 — Ricerca repo per argomento (GitHub Actions)

Una serie di ricerche GitHub su qualunque argomento, lanciate da GitHub Actions. Per ogni ricerca:
una lista di repository (deduplicata, dal più stellato) con una breve descrizione di **cosa ci puoi
fare**. Interno, 0.00.

## Come si lancia

GitHub → Actions → **Ricerca repo per argomento** → Run workflow.

| Campo | Cosa mettere |
|---|---|
| preset | nome di una ricerca salvata in `config/repo_searches.yaml`: `musica-elettronica-audio` (default) o `api-metadati-tracce` (client di MusicBrainz, Discogs, Last.fm, Spotify, Deezer, Beatport, riconoscimento AcoustID/Shazam, tagger) |
| queries | in alternativa, query libere separate da `;` — es. `topic:beat-tracking; techno in:description` |
| min_stars | soglia per le query che non scrivono `stars:` (vuoto = quella del preset) |
| max_per_query | quanti repo per query (default 15) |
| describe | `auto`: descrizione scritta dal modello (serve il secret `OPENAI_API_KEY`); `off`: quella di GitHub |
| save | salva il risultato in `process/research/searches/` con una PR mergiata |

Il risultato è in tre posti: la **Summary** del run (la tabella si legge subito), l'artifact
`repo-search` (Markdown + JSON) e, con `save`, `process/research/searches/<data>_<ricerca>.md`.

Da riga di comando, in locale:

```bash
pip install requests pyyaml openai
python -m scripts.github_research.repo_search --preset musica-elettronica-audio --output out.md
python -m scripts.github_research.repo_search --query "topic:beat-tracking" --query "topic:dj" --min-stars 50
```

## Aggiungere una serie di ricerche

Un blocco nuovo in `config/repo_searches.yaml`:

```yaml
sintetizzatori-software:
  focus: sintetizzatori e plugin audio open source da usare in produzione
  min_stars: 50
  queries:
    - topic:synthesizer
    - topic:vst
  exclude: ['\bmidi\b']
```

`focus` lo legge il modello per scrivere "cosa ci puoi fare" pensando a quello che interessa;
`exclude` / `require` sono espressioni regolari su nome, descrizione e topic.

## Come lavora

1. Ogni query va alla ricerca GitHub (`search/repositories`, ordinata per stelle); `stars:>N` si
   aggiunge da solo se manca. Pausa di 2 secondi tra le query e nuovo tentativo sul limite di
   frequenza (30 ricerche al minuto).
2. I repo trovati da più query compaiono una volta sola, con l'elenco delle query che li hanno
   trovati (in fondo al report). Gli `exclude` tolgono il rumore (es. "audio-analysis" porta
   dentro voce e speech). I repo archiviati restano, segnati "(archiviato)": Demucs lo è ed è
   ancora il riferimento per gli stem.
3. "Cosa ci puoi fare": il modello (`gpt-4o-mini`) legge descrizione, topic e i primi 3.000
   caratteri del README e scrive 1-2 frasi in italiano. Il README è trattato come dato, non come
   istruzioni. Senza chiave, o se il modello sbaglia, resta la descrizione GitHub; il report dice
   quante descrizioni vengono da ciascuna fonte.
   Se la chiave viene rifiutata (401) il modello non viene più chiamato per gli altri repo: un
   solo avviso nel log, e si aggiorna il secret `OPENAI_API_KEY`.

## Limiti

- La ricerca GitHub restituisce al massimo 100 risultati per query e cerca su nome, descrizione,
  topic e README: un repo senza topic e con una descrizione vaga può sfuggire. Per i nomi noti
  conviene una query per nome (`librosa in:name`).
- Gli exclude sono parole: qualche repo fuori tema passa lo stesso (il modello in genere lo dice
  nella descrizione), qualcuno utile può essere scartato.
- Le descrizioni del modello vanno prese come prima idea, non come recensione: non ha provato il
  codice.

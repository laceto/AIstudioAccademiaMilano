# 049 — Il team di ricerca guarda anche GitHub trending

## Cosa cambia

Lo Scout (`scripts/github_research`) oltre alla ricerca per topic legge ora la pagina
**github.com/trending** e tiene i repo che parlano di AI.

- **Dove:** `scripts/github_research/trending.py` (nuovo), chiamato da `search_all_topics()`.
  Vale per tutti quelli che la usano: la CLI `main.py`, il digest settimanale di Gianni
  (`POST /research/run` sul worker) e l'alert giornaliero (`daily_alert.py`, con il trending del giorno).
- **Filtro AI:** parole intere nel nome e nella descrizione (llm, agent, rag, mcp, claude,
  fine-tuning, diffusion, …). Un repo CSS in trending non entra.
- **Dati veri dall'API:** per ogni repo tenuto si chiede `GET /repos/{owner}/{repo}` (topic, data di
  creazione, ultimo push), così l'Analyst lo valuta come gli altri. Il token va solo all'API, mai
  alla pagina HTML. Se l'API non risponde si usano i dati della pagina.
- **Analyst:** il segnale *growth* è il massimo tra la crescita storica (stelle / età) e il ritmo
  attuale (stelle guadagnate nel periodo / giorni). Un repo vecchio che esplode ora sale.
- **Curator:** i repo trending finiscono nelle stesse categorie per topic; il segno "trending"
  resta anche dopo la deduplica.
- **Report:** nuova sezione **Trending on GitHub** (fino a 10 repo, ordinati per stelle guadagnate).
- **Digest di Gianni:** ogni repo salva `trending_stars` e `trending_since`; nella riga che Gianni
  legge compare `(trending +2,345 this week)`. Un campo manomesso viene ignorato.

## Come si usa

```bash
python scripts/github_research/main.py                      # trending settimanale incluso
python scripts/github_research/main.py --trending daily     # oppure monthly
python scripts/github_research/main.py --trending off       # come prima
python scripts/github_research/main.py --trending-language python
```

## Limiti

- GitHub **non ha un'API per il trending**: si legge l'HTML. Se GitHub cambia la pagina, il parser
  restituisce una lista vuota e la ricerca per topic va avanti come prima (nessun errore).
- Una pagina = ~25 repo; con il filtro AI di solito ne restano pochi. Ognuno costa una chiamata API
  (con token: trascurabile; senza token il limite è 60 richieste/ora).
- **Non provato contro la pagina vera:** da questo container github.com risponde 403 (proxy). I test
  usano HTML scritto sul layout attuale (`article.Box-row`). Primo controllo utile: lanciare
  `python scripts/github_research/main.py --topics llm` e guardare la riga
  `N AI repos on GitHub trending`.

## Test

`tests/test_research_trending.py` — 22 test offline (parsing, filtro AI, token solo all'API, pagina
che fallisce, bucket trending, growth, Curator, report, digest e campi manomessi).

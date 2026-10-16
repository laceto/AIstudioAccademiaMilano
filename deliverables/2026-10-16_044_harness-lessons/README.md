# 044 — Lezioni apprese nel learning loop (idea da Harness²)

## Da dove viene

[Harness²](https://github.com/google-research/harness2) (Google Research, Apache 2.0) migliora un agente
senza toccare il modello, solo cambiando ciò che gli sta intorno (prompt, skill, script, memoria). Dopo ogni
esecuzione scrive una **lezione** strutturata e la porta ai compiti successivi:

```
cue:        When a ledger includes credits and debits
lesson:     Include both signs when summing in scripts/summarize.py.
evidence:   removing the positive-only filter changed the probe total…
confidence: high
```

Il learning loop dello studio finora contava soltanto (skill, MCP, successi degli agenti). Adesso registra
anche **cosa** ha insegnato una consegna.

## Cosa cambia

1. **Audit log** — campo opzionale `learning_flags.lessons`:
   ```yaml
   learning_flags:
     risk_score: 1
     lessons:
       - agent: Gianni          # chi la applica; se manca vale per tutto lo studio
         cue: "When ..."        # quando vale
         lesson: "Do ..."       # cosa fare di diverso
         evidence: "NNN: ..."   # cosa si è osservato davvero (obbligatoria)
         confidence: high       # high | medium | low
   ```
2. **`scripts/learning_loop.py`** — `update_lessons()` le salva in `config/global_settings.json` sotto
   `lessons`. La stessa lezione vista di nuovo non viene duplicata: aumenta `seen` e aggiunge richiesta ed
   evidenza; la confidenza resta la più alta vista. Lezioni senza cue, lesson o evidence vengono scartate
   con un messaggio. Rielaborare la stessa richiesta non conta due volte.
3. **`process/lessons_learned.md`** — rigenerato da `write_lessons_md()`, raggruppato per agente, le lezioni
   più forti in alto. Non va modificato a mano. Entra nel commit automatico del loop.
4. **Gianni e Chiara** lo leggono prima di iniziare e applicano le lezioni il cui `cue` corrisponde;
   Gianni le nomina nella spec.

## Come usarlo

Alla chiusura di una consegna, chi scrive l'audit (Francesca) aggiunge 0–3 lezioni, solo se c'è un fatto
osservato. Il loop fa il resto all'hook `Stop`. L'audit 044 contiene già le prime due.

## Limiti

- Le lezioni si leggono, non si applicano da sole: dipende da Gianni e Chiara che leggono il digest.
- Non c'è il ciclo Propose → Probe → Compose automatico di Harness² (rilanciare lo stesso compito con
  varianti dell'harness): costa chiamate al modello e oggi la pipeline non ha un giudice per confrontare.
- La demo di Harness² non è stata eseguita in questa sessione (bloccata dai permessi); il comportamento è
  ricavato dalla lettura del codice.

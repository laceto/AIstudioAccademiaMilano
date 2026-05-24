# Messaggio per Marta — domande prima della v2

> Draft pronto da inviare a Marta (email, WhatsApp, o di persona) prima di consegnarle la v2 a pagamento.
> Recommended by the V2 Team's Devil's Advocate: meglio chiedere ora che rifondere dopo.

---

## Versione email/WhatsApp (italiano informale, ~120 parole)

**Oggetto**: Forno di Marta — due minuti per il sito v2

Ciao Marta,

ho pronta una versione potenziata del tuo sito, ma prima di consegnartela vorrei essere sicuro che sia davvero utile per come lavori tu. Quattro domande rapide:

1. **Menu** — preferiresti aggiornare il menu del giorno tu stessa da un piccolo pannello, oppure è più comodo se mi scrivi e lo aggiorno io?

2. **Email** — quanto spesso controlli la posta elettronica? Una volta al giorno, una alla settimana, mai? (Te lo chiedo perché alcuni clienti del sito potrebbero scriverti lì.)

3. **Calendario** — se il sito prendesse prenotazioni per torte su misura, su quale calendario preferiresti vederle? Google, Apple (iCloud), Outlook?

4. **Anno di fondazione** — sul sito c'è scritto "dal 1987". È giusto?

Rispondi quando puoi, anche con due righe. Grazie!

— Luigi

---

## Cosa fare con le risposte

| Risposta tipica | Cosa significa per il prodotto |
|---|---|
| "Aggiorno io / leggo email / uso Google / 1987 ok" | Marta è candidata perfetta per la **tier commerciale (€45,90)**: CMS + modulo ordini + integrazione Gmail/Calendar. Spediamo la v2 così com'è. |
| "Scrivimi tu / non leggo email / uso Apple / fondato nel 1991" | Tier sbagliata. Scaliamo alla **tier premium (€29,90)**: stessi miglioramenti SEO/OG/JSON-LD/affidabilità, niente CMS, niente modulo ordini. Aggiorniamo l'anno. |
| "In realtà il sito non mi serve molto, i clienti vengono in negozio" | **Caso sunset del DA**: non spediamo niente di nuovo. Marta tiene la v1 (€9,90, già pagata, oggi sistemata con la warranty fix ISS-016). Chiudiamo 011 come "ricerca interna, niente fattura cliente". |

## Cosa NON fare prima di avere le risposte

- ❌ Non emettere INV-011 a Marta (al momento è in stato `drafted` nel log audit di 011)
- ❌ Non spingere il branch `claude/bakery-v2-team` sulla repo di Marta
- ❌ Non attivare Plausible o Sentry (snippet sono commentati nel `site/index.html`)

## Cosa si può fare adesso comunque

- ✅ ISS-016 warranty fix sulla v1 è già consegnata (placeholder image + form sentinel) — non costa nulla a Marta
- ✅ Merge del branch `claude/bakery-v2-team` su `main` della repo AI Studio (è infrastruttura interna, non tocca Marta)
- ✅ Inviare questo messaggio

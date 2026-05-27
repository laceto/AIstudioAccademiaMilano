# Brainstorm: Assistente DIY Impianto Elettrico

**Data:** 2026-05-27  
**Contesto:** Impianto elettrico in cantina 3×4 — assistente dedicato / call center

---

## Problema Core

"Ho una cantina 3x4, devo fare l'impianto. Non so da dove partire, ho paura di sbagliare, un elettricista costa troppo per qualcosa che posso fare io — ma ho bisogno di qualcuno che mi guidi in tempo reale."

---

## Gruppi di Affinità

| Segmento | Trigger | Pain point |
|----------|---------|------------|
| Proprietario di casa bricoleur | Trasloco, ristrutturazione | Paura di non superare il collaudo CEI 64-8 |
| Genitore con cantina da trasformare | Hobby room, palestra, studio bambini | Budget stretto, vuole fare nei weekend |
| Piccolo artigiano / micro-imprenditore | Apertura attività, ampliamento laboratorio | Conosce il mestiere, non l'impianto |
| Piccolo landlord (2-3 appartamenti) | Nuovo inquilino, certificazione | Non vuole chiamare elettricista per "cose semplici" |
| Camperista / barca owner | Preparazione stagione, upgrade 12V | Community forte, cercano esperto |
| Agricoltore / agriturismo | Ampliamento, adeguamento normativo | Lontano dalla città, elettricista caro e lontano |

---

## Format del Prodotto: 3 Ipotesi

| Format | Pro | Contro |
|--------|-----|--------|
| Chat assistente AI (sempre disponibile, step-by-step) | Scalabile, costo basso | Non certificabile, liability |
| Call center esperto (elettricista on-demand, voce/video) | Fiducia alta, personalizzato | Costo operativo, orari |
| Ibrido: AI + escalation umano | Best of both, upsell naturale | Complessità |

---

## Canali con API

| Canale | API | Utilizzo |
|--------|-----|---------|
| Reddit | Reddit API (OAuth2, gratuita) | Monitorare r/italy, r/bricolage — intercettare utenti in tempo reale |
| YouTube Data API | Google API (gratuita, quota limitata) | Commenti con domande senza risposta — marketing intelligence |
| Telegram | Bot API (gratuita) | Delivery del servizio, assistente conversazionale |
| WhatsApp Business | Cloud API (Meta, gratuita fino a 1k conv/mese) | Canale principale per il pubblico bricoleur italiano |
| Leroy Merlin | API prodotti (partner program) | SKU materiale → guida installazione contestuale |
| Facebook Groups | Graph API | Molto limitata — praticamente inutilizzabile in automatico |

---

## Funnel MVP

```
Reddit/YouTube API  →  individua utente con problema
        ↓
WhatsApp/Telegram Bot  →  delivery dell'assistente
        ↓
Leroy Merlin API  →  lista materiali contestuale al progetto
```

---

## Prossimi Passi

- [ ] Prototipare Reddit listener (keyword: "impianto elettrico", "cantina", "fai da te CEI")
- [ ] Bot WhatsApp/Telegram con guida step-by-step norma CEI 64-8
- [ ] Valutare partnership Leroy Merlin / Bricocenter (QR code su packaging)

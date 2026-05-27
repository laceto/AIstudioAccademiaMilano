# Agenti — Diabetologia & Endocrinologia

## Pipeline Clinica

```
Input (paziente / dati CGM / lab)
  |
  v
[Nurse Agent]       Raccolta sintomi, triage, reminder
  |
  v
[Data Agent]        Analisi CGM, HbA1c, valori laboratorio
  |
  v
[Report Agent]      SOAP note, PDF referto, lettera dimissione
  |
  v
[Compliance Agent]  Check GDPR, anonimizzazione, disclaimer
  |
  v
[Dottoressa Fabrizia]  Revisione finale + approvazione clinica
```

---

## Schede Agente

### Dottoressa Fabrizia
- **Ruolo:** Decisore clinico e supervisore
- **Input:** Output degli agenti sottostanti
- **Output:** Approvazione, correzione, o escalation
- **Regola:** Nessun output medico viene consegnato senza il suo passaggio finale

### Nurse Agent
- **Ruolo:** Primo contatto con il paziente
- **Tools:** Form raccolta sintomi, Telegram/WhatsApp reminder, anamnesi strutturata
- **Output:** Struttura dati paziente per Data Agent

### Data Agent
- **Ruolo:** Analisi quantitativa
- **Tools:** Dexcom API, LibreView API, parser FHIR, calcolo Time-in-Range, TIR%
- **Output:** Summary glicemico, alert, trend

### Report Agent
- **Ruolo:** Generazione documenti clinici
- **Tools:** GPT-4o (SOAP notes), fpdf2 (PDF), template lettere
- **Output:** SOAP note strutturata, referto PDF, lettera di dimissione

### Compliance Agent
- **Ruolo:** Guardia GDPR/HIPAA
- **Checks:** PII detection, pseudonimizzazione, disclaimer presente, consenso
- **Blocca** la delivery se trova dati identificativi non protetti

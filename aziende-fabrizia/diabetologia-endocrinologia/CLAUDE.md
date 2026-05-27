# CLAUDE.md — Diabetologia & Endocrinologia (Fabrizia)

Questo file guida Claude Code quando lavora in questa azienda digitale.

---

## Chi è Fabrizia

**Fabrizia Aceto** — Medico specialista in Diabetologia e Endocrinologia.  
Approccio: *modern doctor who uses APIs* — integra strumenti digitali nella pratica clinica quotidiana.  
Obiettivo: prodotti SaaS e agenti AI per pazienti, colleghi e strutture sanitarie.

---

## Dominio Clinico

| Area | Dettaglio |
|------|-----------|
| Diabetologia | T1DM, T2DM, gestione glicemica, CGM (Dexcom/Libre), piani dietetici |
| Endocrinologia | Tiroide, surrenali, asse ipofisi, osteoporosi, PCOS |
| Tecnologia medica | API FHIR, HL7, CGM data, OpenAI per note cliniche |

---

## Agenti Operativi

| Agente | Ruolo |
|--------|-------|
| **Dottoressa Fabrizia** | Decisore clinico — approva output medici |
| **Nurse Agent** | Triaging, raccolta sintomi, reminder farmaci |
| **Data Agent** | Analisi CGM, HbA1c trends, lab results |
| **Report Agent** | Genera SOAP notes, lettere di dimissione, referti |
| **Compliance Agent** | Verifica GDPR/HIPAA, anonimizzazione dati |

---

## Pricing

```json
{
  "soap_note_generator":        "4.90",
  "cgm_analysis_report":        "9.90",
  "patient_monitoring_app":     "19.90",
  "clinical_chatbot":           "19.90",
  "therapy_plan_pdf":           "3.90",
  "endocrine_dashboard":        "14.90",
  "pubmed_researcher_app":      "14.90",
  "avatar_digitale_community":  "19.90",
  "research_radar_app":         "14.90",
  "unknown_product":            null
}
```

**Regola:** `unknown_product: null` blocca la delivery — escalate a Luigi+Fabrizia.

---

## Vincoli di Sicurezza

- **Mai** dati identificativi paziente nel codice o nei log
- Ogni output clinico include disclaimer: *"Strumento di supporto — non sostituisce la visita medica"*
- API keys e credenziali solo in `.env` locale, mai committate
- GDPR: nessun dato sanitario persistito senza consenso esplicito
- Pseudonimizzazione obbligatoria per qualsiasi demo/test

---

## Stack Tecnologico

| Layer | Tecnologia |
|-------|-----------|
| LLM | OpenAI GPT-4o / Claude Sonnet (note cliniche) |
| Framework | LangGraph (workflow agentico), FastAPI |
| Frontend | Streamlit (dashboard), React (patient portal) |
| Dati CGM | Dexcom API, LibreView API, FHIR R4 |
| Database | SQLite locale / Supabase (con RLS) |
| PDF | fpdf2 (referti, lettere) |

---

## Deliverable Completati

| ID | Data | Prodotto | Prezzo |
|----|------|---------|--------|
| F001 | 2026-05-27 | PubMed Researcher — ricerca AI-powered su letteratura diabetologica | 14.90 |
| F002 | 2026-05-27 | Avatar Digitale — Telegram+WhatsApp organizer, community AI, bozze post, sync Drive | 19.90 |
| F003 | 2026-05-27 | Research Radar — OpenAlex + Semantic Scholar + Europe PMC + CrossRef + ClinicalTrials (100% gratuiti) | 14.90 |

---

## Prossimi Prodotti

1. **SOAP Note Generator** — struttura automatica per note cliniche da testo libero
2. **CGM Dashboard** — analisi glicemica da file Dexcom/Libre con insights AI
3. **Patient Reminder Bot** — Telegram/WhatsApp per compliance terapeutica
4. **Endocrine Report PDF** — referto automatico da valori di laboratorio
5. **Clinical Chatbot** — pre-triage Streamlit per pazienti diabetici

"""
ClinicalTrials.gov API v2 — trial clinici attivi, completati, in reclutamento.
Completamente gratuito, no key.
https://clinicaltrials.gov/data-api/api
"""
import requests

BASE = "https://clinicaltrials.gov/api/v2"

PHASE_LABELS = {
    "PHASE1":    "Fase 1",
    "PHASE2":    "Fase 2",
    "PHASE3":    "Fase 3",
    "PHASE4":    "Fase 4",
    "NA":        "N/A",
    "EARLY_PHASE1": "Fase 1 precoce",
}

STATUS_LABELS = {
    "RECRUITING":          "In reclutamento",
    "ACTIVE_NOT_RECRUITING": "Attivo (no reclutamento)",
    "COMPLETED":           "Completato",
    "NOT_YET_RECRUITING":  "Non ancora avviato",
    "TERMINATED":          "Terminato",
    "SUSPENDED":           "Sospeso",
    "WITHDRAWN":           "Ritirato",
}


def search_trials(
    condition: str,
    intervention: str = "",
    status: list[str] | None = None,
    max_results: int = 20,
) -> list[dict]:
    """
    Cerca trial clinici.
    status: ['RECRUITING', 'ACTIVE_NOT_RECRUITING', 'COMPLETED', ...]
    """
    params: dict = {
        "query.cond":  condition,
        "pageSize":    min(max_results, 100),
        "format":      "json",
        "fields":      (
            "NCTId,BriefTitle,OfficialTitle,OverallStatus,Phase,"
            "StartDate,PrimaryCompletionDate,EnrollmentCount,"
            "InterventionName,InterventionType,"
            "BriefSummary,Condition,LeadSponsorName,"
            "LocationCountry,EligibilityCriteria"
        ),
    }
    if intervention:
        params["query.intr"] = intervention
    if status:
        params["filter.overallStatus"] = "|".join(status)

    r = requests.get(f"{BASE}/studies", params=params, timeout=15)
    r.raise_for_status()
    data = r.json()

    results = []
    for study in data.get("studies", []):
        proto = study.get("protocolSection", {})
        id_mod   = proto.get("identificationModule", {})
        status_m = proto.get("statusModule", {})
        desc_m   = proto.get("descriptionModule", {})
        design_m = proto.get("designModule", {})
        interv_m = proto.get("armsInterventionsModule", {})
        elig_m   = proto.get("eligibilityModule", {})
        sponsor_m= proto.get("sponsorCollaboratorsModule", {})
        contacts_m = proto.get("contactsLocationsModule", {})

        phases   = design_m.get("phases", [])
        phase_label = PHASE_LABELS.get(phases[0], phases[0]) if phases else "N/D"

        interventions = [
            i.get("name", "") for i in interv_m.get("interventions", [])
        ][:3]

        countries = list(set(
            loc.get("country", "")
            for loc in contacts_m.get("locations", [])
            if loc.get("country")
        ))[:5]

        raw_status = status_m.get("overallStatus", "")
        results.append({
            "source":       "ClinicalTrials.gov",
            "nct_id":       id_mod.get("nctId", ""),
            "title":        id_mod.get("briefTitle", ""),
            "status":       STATUS_LABELS.get(raw_status, raw_status),
            "phase":        phase_label,
            "start_date":   status_m.get("startDateStruct", {}).get("date", ""),
            "completion":   status_m.get("primaryCompletionDateStruct", {}).get("date", ""),
            "enrollment":   design_m.get("enrollmentInfo", {}).get("count", 0),
            "summary":      desc_m.get("briefSummary", "")[:500],
            "interventions": ", ".join(interventions),
            "sponsor":      sponsor_m.get("leadSponsor", {}).get("name", ""),
            "countries":    ", ".join(countries),
            "url":          f"https://clinicaltrials.gov/study/{id_mod.get('nctId', '')}",
        })
    return results


def get_recruiting_trials(condition: str, max_results: int = 10) -> list[dict]:
    """Solo trial attualmente in reclutamento pazienti."""
    return search_trials(
        condition,
        status=["RECRUITING", "NOT_YET_RECRUITING"],
        max_results=max_results,
    )

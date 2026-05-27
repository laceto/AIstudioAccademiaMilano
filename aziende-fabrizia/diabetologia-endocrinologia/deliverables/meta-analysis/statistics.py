"""
Core meta-analysis statistics.
Supporta: Mean Difference, SMD, OR, RR, HR (log scale per i ratio).
Metodo: DerSimonian-Laird (random effects) + inverse variance (fixed effects).
"""
import numpy as np
from scipy import stats


def se_from_ci(ci_lower: float, ci_upper: float, log_scale: bool = False) -> float:
    """Calcola SE da CI al 95%."""
    if log_scale:
        return (np.log(ci_upper) - np.log(ci_lower)) / (2 * 1.96)
    return (ci_upper - ci_lower) / (2 * 1.96)


def prepare_study(study: dict) -> dict | None:
    """
    Normalizza un studio per la meta-analisi.
    Input atteso:
      effect_size, ci_lower, ci_upper  (oppure effect_size + se)
      effect_measure: 'MD'|'SMD'|'OR'|'RR'|'HR'
    Ritorna None se i dati sono insufficienti.
    """
    log_scale = study.get("effect_measure", "MD") in ("OR", "RR", "HR")

    es = study.get("effect_size")
    if es is None:
        return None

    se = study.get("se")
    if se is None:
        ci_l = study.get("ci_lower")
        ci_u = study.get("ci_upper")
        if ci_l is None or ci_u is None:
            return None
        se = se_from_ci(ci_l, ci_u, log_scale=log_scale)

    if log_scale:
        log_es   = np.log(es)
        log_ci_l = np.log(study.get("ci_lower", es)) if study.get("ci_lower") else log_es - 1.96 * se
        log_ci_u = np.log(study.get("ci_upper", es)) if study.get("ci_upper") else log_es + 1.96 * se
        return {**study, "_log_es": log_es, "_log_ci_l": log_ci_l,
                "_log_ci_u": log_ci_u, "_se": se}

    return {**study, "_log_es": es,
            "_log_ci_l": study.get("ci_lower", es - 1.96 * se),
            "_log_ci_u": study.get("ci_upper", es + 1.96 * se),
            "_se": se}


def run(studies: list[dict], method: str = "random_effects") -> dict:
    """
    Esegue meta-analisi su una lista di studi preparati con prepare_study().
    method: 'random_effects' | 'fixed_effects'
    """
    valid = [s for s in studies if s is not None and s.get("_se") and s["_se"] > 0]
    if len(valid) < 2:
        return {"error": "Servono almeno 2 studi con statistiche valide."}

    log_scale = valid[0].get("effect_measure", "MD") in ("OR", "RR", "HR")

    es_arr = np.array([s["_log_es"] for s in valid])
    se_arr = np.array([s["_se"]     for s in valid])
    k      = len(valid)

    # ── Fixed effects ──────────────────────────────────────────────────────────
    wi      = 1 / se_arr ** 2
    fe_est  = np.sum(wi * es_arr) / np.sum(wi)
    fe_se   = np.sqrt(1 / np.sum(wi))

    # ── Q statistic (Cochran) ──────────────────────────────────────────────────
    Q    = float(np.sum(wi * (es_arr - fe_est) ** 2))
    df   = k - 1
    p_Q  = float(1 - stats.chi2.cdf(Q, df))
    I2   = float(max(0.0, (Q - df) / Q * 100)) if Q > 0 else 0.0

    # ── Tau² (DerSimonian-Laird) ───────────────────────────────────────────────
    C    = float(np.sum(wi) - np.sum(wi ** 2) / np.sum(wi))
    tau2 = float(max(0.0, (Q - df) / C)) if C > 0 else 0.0

    # ── Random effects ─────────────────────────────────────────────────────────
    if method == "random_effects" and tau2 > 0:
        wi_re   = 1 / (se_arr ** 2 + tau2)
        re_est  = float(np.sum(wi_re * es_arr) / np.sum(wi_re))
        re_se   = float(np.sqrt(1 / np.sum(wi_re)))
        weights = (wi_re / np.sum(wi_re) * 100).tolist()
    else:
        re_est  = float(fe_est)
        re_se   = float(fe_se)
        wi_re   = wi
        weights = (wi / np.sum(wi) * 100).tolist()

    re_ci_l = re_est - 1.96 * re_se
    re_ci_u = re_est + 1.96 * re_se
    z       = re_est / re_se
    p_val   = float(2 * (1 - stats.norm.cdf(abs(z))))

    def _back(x):
        return float(np.exp(x)) if log_scale else float(x)

    # Heterogeneity label
    if I2 < 25:   het_label = "Bassa (I²<25%)"
    elif I2 < 50: het_label = "Moderata (25%≤I²<50%)"
    elif I2 < 75: het_label = "Sostanziale (50%≤I²<75%)"
    else:         het_label = "Alta (I²≥75%)"

    return {
        "k":              k,
        "method":         method,
        "log_scale":      log_scale,
        "estimate":       _back(re_est),
        "ci_lower":       _back(re_ci_l),
        "ci_upper":       _back(re_ci_u),
        "p_value":        p_val,
        "Q":              Q,
        "df":             df,
        "p_heterogeneity": p_Q,
        "I2":             I2,
        "tau2":           tau2,
        "heterogeneity":  het_label,
        "study_weights":  weights,
        "valid_studies":  valid,
        # Fixed effects (per confronto)
        "fe_estimate":    _back(float(fe_est)),
        "fe_ci_lower":    _back(float(fe_est - 1.96 * fe_se)),
        "fe_ci_upper":    _back(float(fe_est + 1.96 * fe_se)),
    }


def egger_test(studies: list[dict]) -> dict:
    """
    Test di Egger per publication bias.
    Regresse standard normal deviate vs precisione (1/SE).
    p < 0.05 suggerisce asimmetria nel funnel plot.
    """
    valid = [s for s in studies if s and s.get("_se") and s["_se"] > 0]
    if len(valid) < 3:
        return {"error": "Serve almeno 3 studi per il test di Egger."}

    precision = np.array([1 / s["_se"] for s in valid])
    snd       = np.array([s["_log_es"] / s["_se"] for s in valid])

    slope, intercept, r, p_val, _ = stats.linregress(precision, snd)
    return {
        "intercept": float(intercept),
        "slope":     float(slope),
        "p_value":   float(p_val),
        "bias":      "Possibile bias" if p_val < 0.05 else "Nessun bias significativo",
    }

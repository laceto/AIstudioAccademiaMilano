"""
Visualizzazioni interattive per meta-analisi: forest plot e funnel plot.
"""
import numpy as np
import plotly.graph_objects as go


def forest_plot(
    studies: list[dict],
    meta_result: dict,
    effect_label: str = "Effect Size",
    null_value: float = 0.0,
) -> go.Figure:
    """
    Forest plot interattivo.
    studies: lista di dict con _log_es, _log_ci_l, _log_ci_u, study_name, n_total
    meta_result: output di statistics.run()
    """
    log_scale = meta_result.get("log_scale", False)
    k         = len(studies)
    weights   = meta_result.get("study_weights", [100 / k] * k)

    # Posizioni Y: studi dall'alto verso il basso, pooled in fondo
    y_studies = list(range(k + 2, 2, -1))
    y_pooled  = 1

    fig = go.Figure()

    def _display(x):
        return float(np.exp(x)) if log_scale else float(x)

    # ── Studi individuali ──────────────────────────────────────────────────────
    for i, (study, y, w) in enumerate(zip(studies, y_studies, weights)):
        es  = _display(study["_log_es"])
        cil = _display(study["_log_ci_l"])
        ciu = _display(study["_log_ci_u"])
        n   = study.get("n_total", "?")
        name = study.get("study_name", f"Studio {i+1}")

        # Linea CI
        fig.add_trace(go.Scatter(
            x=[cil, ciu], y=[y, y],
            mode="lines",
            line=dict(color="#475569", width=1.5),
            showlegend=False,
            hoverinfo="skip",
        ))
        # Tick verticali CI
        for x_tick in [cil, ciu]:
            fig.add_trace(go.Scatter(
                x=[x_tick, x_tick], y=[y - 0.15, y + 0.15],
                mode="lines",
                line=dict(color="#475569", width=1.5),
                showlegend=False,
                hoverinfo="skip",
            ))
        # Box (dimensione proporzionale al peso)
        box_size = max(6, min(20, w * 1.2))
        fig.add_trace(go.Scatter(
            x=[es], y=[y],
            mode="markers",
            marker=dict(size=box_size, color="#2563eb", symbol="square"),
            showlegend=False,
            hovertemplate=(
                f"<b>{name}</b><br>"
                f"n = {n}<br>"
                f"{effect_label}: {es:.3f}<br>"
                f"95% CI: [{cil:.3f}, {ciu:.3f}]<br>"
                f"Peso: {w:.1f}%<extra></extra>"
            ),
        ))

    # ── Linea separator ────────────────────────────────────────────────────────
    fig.add_hline(y=1.5, line_dash="dot", line_color="#94a3b8", line_width=1)

    # ── Pooled estimate (diamante) ────────────────────────────────────────────
    est = meta_result["estimate"]
    cil_p = meta_result["ci_lower"]
    ciu_p = meta_result["ci_upper"]
    h     = 0.4

    fig.add_trace(go.Scatter(
        x=[cil_p, est, ciu_p, est, cil_p],
        y=[y_pooled, y_pooled + h, y_pooled, y_pooled - h, y_pooled],
        fill="toself",
        fillcolor="#1d4ed8",
        line=dict(color="#1d4ed8", width=1),
        showlegend=False,
        hovertemplate=(
            f"<b>Stima pooled ({meta_result.get('method','RE')})</b><br>"
            f"{effect_label}: {est:.3f}<br>"
            f"95% CI: [{cil_p:.3f}, {ciu_p:.3f}]<br>"
            f"p = {meta_result.get('p_value', '?'):.4f}<br>"
            f"I² = {meta_result.get('I2', 0):.1f}%<extra></extra>"
        ),
    ))

    # ── Linea al valore nullo ─────────────────────────────────────────────────
    fig.add_vline(
        x=null_value,
        line_dash="dash",
        line_color="#ef4444",
        line_width=1,
        annotation_text="Nessun effetto",
        annotation_position="top right",
        annotation_font_size=10,
    )

    # ── Annotazioni Y ─────────────────────────────────────────────────────────
    y_tickvals = y_studies + [y_pooled]
    y_ticktext = [s.get("study_name", f"Studio {i+1}") for i, s in enumerate(studies)] + ["Pooled (RE)"]

    # Statistiche eterogeneità nel titolo
    het_text = (
        f"k={k} studi | I²={meta_result.get('I2',0):.1f}% | "
        f"τ²={meta_result.get('tau2',0):.4f} | "
        f"Q={meta_result.get('Q',0):.2f} (p={meta_result.get('p_heterogeneity',1):.3f})"
    )

    fig.update_layout(
        title=dict(
            text=f"<b>Forest Plot — {effect_label}</b><br><sup>{het_text}</sup>",
            font=dict(size=14),
        ),
        xaxis_title=effect_label,
        yaxis=dict(
            tickvals=y_tickvals,
            ticktext=y_ticktext,
            showgrid=False,
            zeroline=False,
        ),
        height=max(450, 55 * (k + 3)),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        margin=dict(l=200, r=80, t=90, b=60),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#f1f5f9")

    return fig


def funnel_plot(
    studies: list[dict],
    meta_result: dict,
    effect_label: str = "Effect Size",
    egger: dict | None = None,
) -> go.Figure:
    """
    Funnel plot per visual check del publication bias.
    Se simmetrico → nessun bias evidente.
    """
    log_scale = meta_result.get("log_scale", False)

    def _display(x):
        return float(np.exp(x)) if log_scale else float(x)

    es_vals  = [_display(s["_log_es"]) for s in studies]
    se_vals  = [s["_se"] for s in studies]
    names    = [s.get("study_name", f"S{i}") for i, s in enumerate(studies)]
    pooled   = meta_result["estimate"]

    fig = go.Figure()

    # ── Punti studi ────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=es_vals,
        y=se_vals,
        mode="markers",
        marker=dict(size=9, color="#2563eb", opacity=0.8),
        text=names,
        hovertemplate="<b>%{text}</b><br>ES: %{x:.3f}<br>SE: %{y:.3f}<extra></extra>",
        showlegend=False,
    ))

    # ── Cono simmetria intorno alla stima pooled ───────────────────────────────
    se_max = max(se_vals) * 1.1
    se_range = np.linspace(0, se_max, 100)
    fig.add_trace(go.Scatter(
        x=pooled + 1.96 * se_range,
        y=se_range,
        mode="lines",
        line=dict(color="#94a3b8", dash="dash", width=1),
        showlegend=False,
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=pooled - 1.96 * se_range,
        y=se_range,
        mode="lines",
        line=dict(color="#94a3b8", dash="dash", width=1),
        showlegend=False,
        hoverinfo="skip",
        fill="tonexty",
        fillcolor="rgba(148,163,184,0.08)",
    ))

    # ── Linea verticale alla stima pooled ─────────────────────────────────────
    fig.add_vline(x=pooled, line_dash="solid", line_color="#1d4ed8", line_width=1.5)

    egger_text = ""
    if egger and not egger.get("error"):
        egger_text = (
            f" | Egger: intercetta={egger['intercept']:.3f} "
            f"p={egger['p_value']:.3f} — {egger['bias']}"
        )

    fig.update_layout(
        title=f"<b>Funnel Plot</b>{egger_text}",
        xaxis_title=effect_label,
        yaxis=dict(
            title="Standard Error",
            autorange="reversed",
            showgrid=True,
            gridcolor="#f1f5f9",
        ),
        height=420,
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )

    return fig

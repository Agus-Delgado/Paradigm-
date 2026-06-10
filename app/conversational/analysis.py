"""Orquestador de análisis contextual basado en respuestas del usuario."""

from __future__ import annotations

import pandas as pd

from app.conversational.dataset_snapshot import DatasetSnapshot, build_dataset_snapshot
from app.conversational.domain import domain_label_es
from app.conversational.legacy_bridge import (
    compute_clinic_kpis,
    insights_build_dataset_overview,
    insights_compare_categorical_numeric,
    insights_compare_clinic_especialidad_ingreso,
    insights_compare_clinic_estado,
    insights_detect_outliers,
    insights_pick_compare_pair,
    insights_top_categories,
)
from app.conversational.plan import build_analysis_plan
from app.conversational.types import AnalysisPlan, ContextualAnalysisResult, Domain, ScoredRecommendation

_IMPACT_ORDER = {"Alto": 0, "Medio": 1, "Bajo": 2}


def _segment_outlier_insight(
    df: pd.DataFrame,
    segment_col: str,
    metric_col: str,
    *,
    higher_is_worse: bool = True,
) -> str | None:
    if segment_col not in df.columns or metric_col not in df.columns:
        return None
    sub = df[[segment_col, metric_col]].copy()
    sub[metric_col] = pd.to_numeric(sub[metric_col], errors="coerce")
    sub = sub.dropna(subset=[metric_col])
    if sub.empty:
        return None
    agg = sub.groupby(segment_col, as_index=False)[metric_col].mean()
    if len(agg) < 2:
        return None
    overall = float(sub[metric_col].mean())
    worst = agg.loc[agg[metric_col].idxmax() if higher_is_worse else agg[metric_col].idxmin()]
    seg_name = worst[segment_col]
    seg_val = float(worst[metric_col])
    delta = ((seg_val - overall) / overall * 100.0) if overall else 0.0
    direction = "por encima" if seg_val > overall else "por debajo"
    return (
        f"**Posible causa raíz:** «{seg_name}» concentra la señal — "
        f"{metric_col} {direction} del promedio ({seg_val:.2f} vs {overall:.2f}, "
        f"Δ {delta:+.1f}%). Validá tu hipótesis en este segmento."
    )


def _format_top_values(snapshot: DatasetSnapshot, col: str, n: int = 2) -> str:
    tops = snapshot.top_values.get(col, ())
    if not tops:
        return ""
    return ", ".join(f"«{v}»" for v, _ in tops[:n])


def _recommendations_for_plan(
    plan: AnalysisPlan,
    df: pd.DataFrame,
    snapshot: DatasetSnapshot | None = None,
) -> list[ScoredRecommendation]:
    recs: list[ScoredRecommendation] = []
    obj = plan.objective
    segment = plan.segment_col
    snap = snapshot

    if plan.domain == "healthcare_clinic":
        seg = segment or "especialidad"
        top_seg = _format_top_values(snap, seg) if snap else ""
        canal_col = next((c for c in (snap.segment_columns if snap else ()) if "canal" in c.lower()), None)
        top_canal = _format_top_values(snap, canal_col) if snap and canal_col else ""
        detail = top_seg or (snap.notable_contrast if snap else "")
        canal_part = f" vía canal {top_canal}" if top_canal else ""
        recs.append(
            ScoredRecommendation(
                impact="Alto",
                text=(
                    f"Investigá ausencias en {detail or seg}{canal_part}: "
                    "priorizá confirmación activa donde la tasa supere el promedio global."
                ),
            )
        )
        if "ingreso_neto" in df.columns:
            recs.append(
                ScoredRecommendation(
                    impact="Alto",
                    text=(
                        "Cruzá «ingreso_neto» con «estado_turno» para cuantificar pérdida "
                        f"por no-shows evitables{(' en ' + top_seg) if top_seg else ''}."
                    ),
                )
            )
        recs.append(
            ScoredRecommendation(
                impact="Medio",
                text=(
                    f"Definí umbral de acción (ej. >15% ausencias) y asigná recordatorios "
                    f"al segmento outlier{(' (' + top_seg + ')') if top_seg else ''}."
                ),
            )
        )
        recs.append(
            ScoredRecommendation(
                impact="Bajo",
                text="Monitoreá tendencia semanal de ausencias para detectar cambios estructurales post-intervención.",
            )
        )

    elif plan.domain == "healthcare_mart":
        seg = segment or "specialty_name"
        top_seg = _format_top_values(snap, seg) if snap else ""
        contrast = snap.notable_contrast if snap else None
        target = contrast or top_seg or seg
        recs.append(
            ScoredRecommendation(
                impact="Alto",
                text=(
                    f"Priorizá anti no-show en {target} con tasa superior al promedio; "
                    "simulá impacto en el tab No-Show ML."
                ),
            )
        )
        recs.append(
            ScoredRecommendation(
                impact="Medio",
                text="Contrastá citas ATTENDED vs facturación si sospechás brechas de conciliación.",
            )
        )
        recs.append(
            ScoredRecommendation(
                impact="Bajo",
                text="Monitoreá tendencia semanal de NO_SHOW para detectar sobre-agenda o fallas de confirmación.",
            )
        )

    elif plan.domain == "finance":
        metric = plan.metric_col or (snap.metric_columns[0] if snap and snap.metric_columns else "variacion_pct")
        seg = segment or (snap.segment_columns[0] if snap and snap.segment_columns else "centro_costo")
        top_seg = _format_top_values(snap, seg) if snap else ""
        outlier_note = ""
        if snap and snap.outlier_columns:
            outlier_note = f"; revisá outliers en «{snap.outlier_columns[0]}»"
        contrast = f" ({snap.notable_contrast})" if snap and snap.notable_contrast else ""
        recs.append(
            ScoredRecommendation(
                impact="Alto",
                text=(
                    f"Segmentá «{metric}» por «{seg}»{contrast} "
                    f"para aislar el driver del desvío{outlier_note}."
                    + (f" Valores a vigilar: {top_seg}." if top_seg else "")
                ),
            )
        )
        recs.append(
            ScoredRecommendation(
                impact="Medio",
                text="Validá outliers contra reglas de negocio y contratos antes de ajustar presupuesto.",
            )
        )
        if plan.outlier_threshold_pct:
            recs.append(
                ScoredRecommendation(
                    impact="Medio",
                    text=f"Documentá alertas recurrentes con umbral del {plan.outlier_threshold_pct:.0f}% acordado.",
                )
            )
        period_note = snap.temporal_hint if snap and snap.temporal_hint else "periodo"
        recs.append(
            ScoredRecommendation(
                impact="Bajo",
                text=f"Revisá estacionalidad por {period_note} para descartar efectos temporales en el desvío.",
            )
        )

    elif plan.domain == "operations":
        metric = plan.metric_col or (snap.metric_columns[0] if snap and snap.metric_columns else "defectos")
        seg = segment or (snap.segment_columns[0] if snap and snap.segment_columns else "planta")
        top_seg = _format_top_values(snap, seg) if snap else ""
        contrast = snap.notable_contrast if snap else None
        target = contrast or top_seg or seg
        recs.append(
            ScoredRecommendation(
                impact="Alto",
                text=(
                    f"Auditar {target} con peor «{metric}»: "
                    "revisar mantenimiento, capacitación y turnos."
                ),
            )
        )
        ciclo_note = ""
        if "tiempo_ciclo_min" in df.columns and snap:
            turno_tops = _format_top_values(snap, "turno")
            if turno_tops:
                ciclo_note = f" (turno {turno_tops} con ciclos largos)"
        recs.append(
            ScoredRecommendation(
                impact="Medio",
                text=f"Correlacionar «defectos» con «tiempo_ciclo_min»{ciclo_note} para distinguir capacidad vs calidad.",
            )
        )
        recs.append(
            ScoredRecommendation(
                impact="Bajo",
                text="Establecer control chart semanal por línea para detectar deriva temprana.",
            )
        )

    else:
        metric = plan.metric_col or (snap.metric_columns[0] if snap and snap.metric_columns else "métrica clave")
        seg = segment or (snap.segment_columns[0] if snap and snap.segment_columns else "segmento")
        top_seg = _format_top_values(snap, seg) if snap else ""
        vocab = ", ".join(snap.vocabulary[:2]) if snap and snap.vocabulary else "tu dominio"
        contrast = snap.notable_contrast if snap else None
        recs.append(
            ScoredRecommendation(
                impact="Alto",
                text=(
                    f"Contrastá «{metric}» por «{seg}»"
                    + (f" ({top_seg})" if top_seg else "")
                    + (f" — {contrast}" if contrast else "")
                    + f" para validar tu hipótesis en contexto de {vocab}."
                ),
            )
        )
        if snap and snap.outlier_columns:
            recs.append(
                ScoredRecommendation(
                    impact="Medio",
                    text=f"Revisá outliers detectados en «{snap.outlier_columns[0]}» antes de decisiones operativas.",
                )
            )
        else:
            recs.append(
                ScoredRecommendation(
                    impact="Medio",
                    text="Completá perfil de nulos y duplicados antes de decisiones operativas.",
                )
            )
        recs.append(
            ScoredRecommendation(
                impact="Bajo",
                text="Evitá conclusiones causales sin contraste temporal o benchmark externo.",
            )
        )

    if plan.hypothesis:
        recs.insert(
            0,
            ScoredRecommendation(
                impact="Alto",
                text=f"Hipótesis declarada: «{plan.hypothesis}» — contrastala con el segmento outlier del análisis.",
            ),
        )

    if obj:
        recs.insert(
            0,
            ScoredRecommendation(
                impact="Alto",
                text=f"Objetivo: «{obj}» — priorizá acciones que muevan directamente esta métrica de negocio.",
            ),
        )

    recs.sort(key=lambda r: _IMPACT_ORDER.get(r.impact, 9))
    return recs[:6]


def run_contextual_analysis(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    profile,
    findings: list,
    answers: dict[str, str | float],
    domain: Domain,
) -> ContextualAnalysisResult:
    snapshot = build_dataset_snapshot(df, logical_types, profile, domain, findings)
    plan = build_analysis_plan(
        answers,
        domain,
        logical_types,
        df=df,
        profile=profile,
        findings=findings,
        snapshot=snapshot,
    )
    domain_es = domain_label_es(domain)

    overview = insights_build_dataset_overview(df, profile, logical_types)
    finding_bullets: list[str] = list(overview[:2])
    data_used: list[str] = []

    finding_bullets.extend(insights_top_categories(df, logical_types, limit_cols=2))

    if domain == "healthcare_clinic":
        estado = insights_compare_clinic_estado(df)
        if estado:
            finding_bullets.append(estado)
        esp = insights_compare_clinic_especialidad_ingreso(df)
        if esp:
            finding_bullets.append(esp)
        kpis = compute_clinic_kpis(df)
        finding_bullets.append(
            f"Tasa de ausencia global: {kpis['pct_ausente']:.1f}% ({kpis['n_turnos']:,} turnos)."
        )
        data_used.append("estado_turno")
        if "especialidad" in df.columns:
            est = df["estado_turno"].astype(str).str.strip().str.lower()
            by_esp = df.assign(_ausente=(est == "ausente").astype(int)).groupby("especialidad")["_ausente"].mean()
            if len(by_esp) >= 2:
                worst_esp = by_esp.idxmax()
                finding_bullets.append(
                    f"**Posible causa raíz:** «{worst_esp}» concentra la mayor tasa de ausencia "
                    f"({by_esp.max() * 100:.1f}% vs promedio {by_esp.mean() * 100:.1f}%)."
                )

    elif domain == "healthcare_mart":
        if "status_code" in df.columns:
            attended = int((df["status_code"] == "ATTENDED").sum())
            noshow = int((df["status_code"] == "NO_SHOW").sum())
            denom = attended + noshow
            rate = (noshow / denom * 100.0) if denom else 0.0
            finding_bullets.append(
                f"Tasa de no-show (ATTENDED+NO_SHOW): {rate:.1f}% ({noshow:,} de {denom:,} citas elegibles)."
            )
            data_used.append("status_code")
            segment = plan.segment_col or "specialty_name"
            if segment in df.columns:
                sub = df[[segment, "status_code"]].copy()
                rows: list[tuple[str, float]] = []
                for seg, grp in sub.groupby(segment):
                    a = int((grp["status_code"] == "ATTENDED").sum())
                    ns = int((grp["status_code"] == "NO_SHOW").sum())
                    d = a + ns
                    if d >= 5:
                        rows.append((str(seg), ns / d * 100.0))
                if rows:
                    worst = max(rows, key=lambda x: x[1])
                    finding_bullets.append(
                        f"**Posible causa raíz:** «{worst[0]}» con no-show rate {worst[1]:.1f}% — "
                        "validá política de confirmación en este segmento."
                    )

    elif domain == "operations":
        metric = plan.metric_col or "defectos"
        segment = plan.segment_col or "planta"
        root = _segment_outlier_insight(df, segment, metric)
        if root:
            finding_bullets.append(root)
        if "tiempo_ciclo_min" in df.columns and "turno" in df.columns:
            by_turno = df.groupby("turno")["tiempo_ciclo_min"].mean()
            if len(by_turno) >= 2:
                worst_turno = by_turno.idxmax()
                finding_bullets.append(
                    f"Turno «{worst_turno}» con mayor tiempo de ciclo ({by_turno.max():.1f} min vs "
                    f"promedio {by_turno.mean():.1f} min) — posible factor de capacidad."
                )

    outlier_findings, outlier_cols = insights_detect_outliers(df, logical_types)
    if plan.outlier_threshold_pct or plan.domain in ("finance", "operations"):
        finding_bullets.extend(outlier_findings[:2])
        data_used.extend(outlier_cols[:2])

    pair = insights_pick_compare_pair(df, logical_types)
    metric = plan.metric_col
    segment = plan.segment_col
    if pair and not (metric and segment):
        if not segment:
            segment = pair[0]
        if not metric:
            metric = pair[1]
    if metric and segment and metric in df.columns and segment in df.columns:
        cmp = insights_compare_categorical_numeric(df, segment, metric)
        if cmp:
            finding_bullets.append(cmp)
            data_used.extend([segment, metric])
        root = _segment_outlier_insight(
            df,
            segment,
            metric,
            higher_is_worse=plan.domain != "generic",
        )
        if root and root not in finding_bullets:
            finding_bullets.append(root)

    quality_warnings = [f.message for f in findings if getattr(f, "severity", "") == "warning"][:2]
    finding_bullets.extend(quality_warnings)

    hypothesis_line = ""
    if plan.hypothesis:
        hypothesis_line = f" Tu hipótesis: «{plan.hypothesis}»."

    contrast_line = ""
    if snapshot.notable_contrast:
        contrast_line = f" Señal destacada: {snapshot.notable_contrast}."

    summary = (
        f"**Resumen ejecutivo** — Dominio {domain_es}. "
        f"Objetivo: «{plan.objective}».{hypothesis_line}{contrast_line} "
        f"Paradigm analizó {profile.row_count:,} filas y {profile.column_count} columnas "
        f"buscando concentraciones que expliquen la causa raíz, no solo síntomas."
    )

    recommendations = _recommendations_for_plan(plan, df, snapshot)

    title = f"Insights — {domain_es}"
    if plan.objective:
        short_obj = plan.objective[:60] + ("…" if len(plan.objective) > 60 else "")
        title = f"Insights: {short_obj}"

    return ContextualAnalysisResult(
        title=title,
        summary=summary,
        findings=finding_bullets[:10],
        recommendations=recommendations,
        data_used=list(dict.fromkeys(data_used))[:8],
        domain_label=domain_es,
    )

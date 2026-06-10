"""Extracción de contexto concreto del dataset para hints y recomendaciones."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.conversational.domain import extract_column_vocabulary
from app.conversational.legacy_bridge import insights_detect_outliers, insights_pick_compare_pair
from app.conversational.types import Domain

_MIN_GROUP_ROWS = 5
_MAX_HINT_VAL_LEN = 42


def _min_group_rows(n_rows: int) -> int:
    if n_rows < 12:
        return 2
    if n_rows < 30:
        return 3
    return _MIN_GROUP_ROWS


@dataclass(frozen=True)
class DatasetSnapshot:
    metric_columns: tuple[str, ...]
    segment_columns: tuple[str, ...]
    top_values: dict[str, tuple[tuple[str, float], ...]]
    outlier_columns: tuple[str, ...]
    compare_pair: tuple[str, str] | None
    notable_contrast: str | None
    vocabulary: tuple[str, ...]
    temporal_hint: str | None = None


def _truncate_val(value: str, max_len: int = _MAX_HINT_VAL_LEN) -> str:
    text = str(value).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _quote(value: str) -> str:
    return f"«{_truncate_val(value)}»"


def _numeric_columns(logical_types: dict[str, str]) -> list[str]:
    return [c for c, t in logical_types.items() if t == "numeric"]


def _categorical_columns(logical_types: dict[str, str]) -> list[str]:
    return [c for c, t in logical_types.items() if t == "categorical"]


def _top_categorical_values(df: pd.DataFrame, col: str, n: int = 3) -> tuple[tuple[str, float], ...]:
    raw = df[col].dropna()
    if raw.empty:
        return ()
    nunique = int(raw.nunique())
    if nunique < 2 or nunique > 50:
        return ()
    vc = raw.astype(str).value_counts()
    total = float(len(raw))
    return tuple((str(k), float(v) / total * 100.0) for k, v in vc.head(n).items())


def _pick_finance_metrics(columns: list[str], logical_types: dict[str, str]) -> list[str]:
    keywords = ("ingreso", "costo", "margen", "presupuesto", "neto", "factura", "monto", "total", "real", "variacion")
    scored: list[tuple[int, str]] = []
    for col in columns:
        if logical_types.get(col) != "numeric":
            continue
        norm = col.lower()
        score = sum(2 for kw in keywords if kw in norm)
        if score > 0:
            scored.append((score, col))
    scored.sort(key=lambda x: (-x[0], x[1]))
    if scored:
        return [c for _, c in scored[:6]]
    return _numeric_columns(logical_types)[:6]


def _score_categorical_col(df: pd.DataFrame, col: str) -> int:
    n = int(df[col].dropna().nunique())
    if n < 2:
        return -1
    if n > 50:
        return 0
    return len(df) - abs(n - 5)


def _rank_segment_columns(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
) -> tuple[str, ...]:
    preferred: tuple[str, ...] = ()
    if domain == "healthcare_clinic":
        preferred = ("especialidad", "medio_pago", "cobertura_medica", "canal_reserva", "channel_code")
    elif domain == "healthcare_mart":
        preferred = ("specialty_name", "provider_label", "channel_code", "coverage_name")
    elif domain == "finance":
        preferred = ("centro_costo", "cuenta", "cliente", "periodo", "moneda")
    elif domain == "operations":
        preferred = ("planta", "linea", "turno", "linea_produccion")

    opts: list[str] = []
    for col in preferred:
        if col in df.columns and logical_types.get(col) in ("categorical", "datetime", "text"):
            opts.append(col)
        elif col in df.columns and logical_types.get(col) == "numeric" and domain == "finance":
            opts.append(col)

    ranked: list[tuple[int, str]] = []
    for col in _categorical_columns(logical_types):
        if col in opts:
            continue
        score = _score_categorical_col(df, col)
        if score >= 0:
            ranked.append((score, col))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    for _, col in ranked:
        if col not in opts:
            opts.append(col)
        if len(opts) >= 5:
            break

    return tuple(opts) if opts else ()


def _rank_metric_columns(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
) -> tuple[str, ...]:
    columns = list(df.columns)
    if domain == "finance":
        return tuple(_pick_finance_metrics(columns, logical_types))
    if domain == "healthcare_clinic":
        for c in ("ingreso_neto", "monto_consulta", "copago"):
            if c in logical_types and logical_types[c] == "numeric":
                return (c,) + tuple(x for x in _numeric_columns(logical_types) if x != c)[:5]
    if domain == "operations":
        for c in ("defectos", "tasa_defecto_pct", "tiempo_ciclo_min", "unidades"):
            if c in logical_types:
                return (c,) + tuple(x for x in _numeric_columns(logical_types) if x != c)[:5]
    if domain == "healthcare_mart":
        nums = _numeric_columns(logical_types)
        return tuple(nums[:6])
    return tuple(_numeric_columns(logical_types)[:6])


def _worst_segment_mean(
    df: pd.DataFrame,
    segment_col: str,
    metric_col: str,
    *,
    higher_is_worse: bool = True,
    min_rows: int | None = None,
) -> tuple[str, float, float] | None:
    if segment_col not in df.columns or metric_col not in df.columns:
        return None
    min_rows = min_rows if min_rows is not None else _min_group_rows(len(df))
    sub = df[[segment_col, metric_col]].copy()
    sub[metric_col] = pd.to_numeric(sub[metric_col], errors="coerce")
    sub = sub.dropna(subset=[metric_col])
    if sub.empty:
        return None
    grp = sub.groupby(sub[segment_col].astype(str), dropna=False)[metric_col]
    stats = grp.agg(["mean", "count"])
    stats = stats[stats["count"] >= min_rows]
    if len(stats) < 2:
        return None
    overall = float(sub[metric_col].mean())
    idx = stats["mean"].idxmax() if higher_is_worse else stats["mean"].idxmin()
    seg_val = float(stats.loc[idx, "mean"])
    return str(idx), seg_val, overall


def _temporal_hint(df: pd.DataFrame, logical_types: dict[str, str]) -> str | None:
    for col in df.columns:
        if logical_types.get(col) != "datetime":
            continue
        dt = pd.to_datetime(df[col], errors="coerce").dropna()
        if dt.empty:
            continue
        q_counts = dt.dt.to_period("Q").astype(str).value_counts()
        if len(q_counts) >= 1:
            top_q = q_counts.index[0]
            return f"periodo {top_q}"
    for col in ("periodo", "mes", "trimestre", "quarter"):
        if col not in df.columns:
            continue
        tops = _top_categorical_values(df, col, n=1)
        if tops:
            return f"{col} {_quote(tops[0][0])}"
    return None


def _clinic_hypothesis_sentence(df: pd.DataFrame) -> str | None:
    if "estado_turno" not in df.columns or "especialidad" not in df.columns:
        return None
    min_rows = _min_group_rows(len(df))
    est = df["estado_turno"].astype(str).str.strip().str.lower()
    work = df.assign(_ausente=(est == "ausente").astype(int))
    by_esp = work.groupby("especialidad")["_ausente"].agg(["mean", "count"])
    by_esp = by_esp[by_esp["count"] >= min_rows]
    if len(by_esp) < 2:
        return None
    worst_esp = str(by_esp["mean"].idxmax())

    canal_col = next((c for c in ("canal_reserva", "channel_code") if c in df.columns), None)
    if canal_col:
        sub = work[work["especialidad"] == worst_esp]
        if len(sub) >= min_rows:
            by_canal = sub.groupby(sub[canal_col].astype(str))["_ausente"].mean()
            if len(by_canal) >= 1:
                canal_val = str(by_canal.idxmax())
                return (
                    f"{_quote(worst_esp)} tiene muchos ausentes porque el canal "
                    f"{_quote(canal_val)} no confirma turnos"
                )
    return f"{_quote(worst_esp)} concentra la mayor tasa de ausencias del consultorio"


def _clinic_notable_contrast(df: pd.DataFrame) -> str | None:
    if "estado_turno" not in df.columns or "especialidad" not in df.columns:
        return None
    est = df["estado_turno"].astype(str).str.strip().str.lower()
    work = df.assign(_ausente=(est == "ausente").astype(int))
    by_esp = work.groupby("especialidad")["_ausente"].agg(["mean", "count"])
    by_esp = by_esp[by_esp["count"] >= min_rows]
    if len(by_esp) < 2:
        return None
    worst_esp = by_esp["mean"].idxmax()
    rate = float(by_esp.loc[worst_esp, "mean"]) * 100.0

    canal_col = next((c for c in ("canal_reserva", "channel_code") if c in df.columns), None)
    canal_val = None
    if canal_col:
        sub = work[work["especialidad"] == worst_esp]
        if len(sub) >= min_rows:
            by_canal = sub.groupby(sub[canal_col].astype(str))["_ausente"].mean()
            if len(by_canal) >= 1:
                canal_val = str(by_canal.idxmax())

    esp_q = _quote(worst_esp)
    if canal_val:
        return (
            f"{esp_q} concentra ausencias ({rate:.0f}%) — "
            f"canal {_quote(canal_val)} aparece entre los más afectados"
        )
    return f"{esp_q} concentra la mayor tasa de ausencias ({rate:.0f}%)"




def _mart_notable_contrast(df: pd.DataFrame) -> str | None:
    if "status_code" not in df.columns:
        return None
    segment = next((c for c in ("specialty_name", "provider_label") if c in df.columns), None)
    if not segment:
        return None
    sub = df[[segment, "status_code"]].copy()
    rows: list[tuple[str, float]] = []
    for seg, grp in sub.groupby(segment):
        a = int((grp["status_code"] == "ATTENDED").sum())
        ns = int((grp["status_code"] == "NO_SHOW").sum())
        d = a + ns
        if d >= _min_group_rows(len(df)):
            rows.append((str(seg), ns / d * 100.0))
    if len(rows) < 2:
        return None
    worst = max(rows, key=lambda x: x[1])
    return f"{_quote(worst[0])} con no-show rate {worst[1]:.1f}%"


def _finance_notable_contrast(df: pd.DataFrame, logical_types: dict[str, str]) -> str | None:
    min_rows = _min_group_rows(len(df))
    metric = next((c for c in ("variacion_pct", "real", "presupuesto", "desvio_pct", "monto_factura") if c in df.columns), None)
    if not metric:
        nums = _rank_metric_columns(df, logical_types, "finance")
        metric = nums[0] if nums else None
    if not metric:
        return None

    centro = "centro_costo" if "centro_costo" in df.columns else None
    cuenta = "cuenta" if "cuenta" in df.columns else None

    if centro and cuenta:
        sub = df[[centro, cuenta, metric]].copy()
        sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
        sub = sub.dropna(subset=[metric])
        if len(sub) >= min_rows:
            sub["_key"] = sub[centro].astype(str) + " / " + sub[cuenta].astype(str)
            agg = sub.groupby("_key")[metric].mean()
            if len(agg) >= 2:
                worst = agg.idxmax()
                val = float(agg.max())
                return f"mayor desvío en {_quote(worst)} ({metric} {val:+.1f}%)"

    segment = centro or cuenta or next(
        (c for c in _rank_segment_columns(df, logical_types, "finance") if c in df.columns and c not in ("periodo", "moneda")),
        None,
    ) or next(iter(_rank_segment_columns(df, logical_types, "finance")), None)
    if segment:
        worst = _worst_segment_mean(df, segment, metric, min_rows=min_rows)
        if worst:
            seg_name, seg_val, _ = worst
            return f"«{metric}» peor en {_quote(seg_name)} ({seg_val:+.2f})"
    return None


def _operations_notable_contrast(df: pd.DataFrame, logical_types: dict[str, str]) -> str | None:
    min_rows = _min_group_rows(len(df))
    metric = next((c for c in ("defectos", "tasa_defecto_pct", "tiempo_ciclo_min") if c in df.columns), None)
    if not metric:
        nums = _rank_metric_columns(df, logical_types, "operations")
        metric = nums[0] if nums else None
    if not metric:
        return None

    planta = "planta" if "planta" in df.columns else None
    linea = "linea" if "linea" in df.columns else None

    if planta and linea:
        sub = df[[planta, linea, metric]].copy()
        sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
        sub = sub.dropna(subset=[metric])
        if len(sub) >= min_rows:
            agg = sub.groupby([planta, linea])[metric].mean()
            if len(agg) >= 2:
                idx = agg.idxmax()
                val = float(agg.max())
                return f"{_quote(idx[0])} en {_quote(idx[1])} con mayor «{metric}» ({val:.2f})"

    segment = planta or linea or "turno" if "turno" in df.columns else None
    if segment:
        worst = _worst_segment_mean(df, segment, metric)
        if worst:
            seg_name, seg_val, _ = worst
            return f"«{metric}» peor en {_quote(seg_name)} ({seg_val:.2f})"
    return None


def _generic_notable_contrast(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    compare_pair: tuple[str, str] | None,
) -> str | None:
    if not compare_pair:
        return None
    seg_col, metric_col = compare_pair
    worst = _worst_segment_mean(df, seg_col, metric_col)
    if not worst:
        return None
    seg_name, seg_val, overall = worst
    delta = ((seg_val - overall) / overall * 100.0) if overall else 0.0
    return (
        f"«{metric_col}» en {_quote(seg_name)} "
        f"({seg_val:.2g} vs promedio {overall:.2g}, Δ {delta:+.0f}%)"
    )


def _detect_notable_contrast(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    domain: Domain,
    compare_pair: tuple[str, str] | None,
) -> str | None:
    if df is None or df.empty or len(df) < 2:
        return None
    if domain == "healthcare_clinic":
        return _clinic_hypothesis_sentence(df) or _clinic_notable_contrast(df)
    if domain == "healthcare_mart":
        return _mart_notable_contrast(df)
    if domain == "finance":
        return _finance_notable_contrast(df, logical_types)
    if domain == "operations":
        return _operations_notable_contrast(df, logical_types)
    return _generic_notable_contrast(df, logical_types, compare_pair)


_FALLBACK_HYPOTHESIS: dict[Domain, str] = {
    "healthcare_clinic": "Ej.: «Cardiología tiene muchos ausentes porque el canal teléfono no confirma turnos».",
    "healthcare_mart": "Ej.: «No-shows altos en ciertas especialidades por falta de recordatorio».",
    "finance": "Ej.: «Operaciones en Planta Logística supera presupuesto por sobrecostos logísticos».",
    "operations": "Ej.: «Planta B con defectos altos en Ensamble por desgaste de maquinaria».",
    "generic": "Describí la señal problemática y tu explicación inicial (hipótesis de causa).",
}


def _fallback_hypothesis_from_tops(snapshot: DatasetSnapshot, domain: Domain) -> str | None:
    usable_cols = [c for c in snapshot.segment_columns if not c.startswith("—")]
    if not usable_cols:
        return None
    seg_col = next((c for c in usable_cols if c in snapshot.top_values), usable_cols[0])
    tops = snapshot.top_values.get(seg_col, ())
    if not tops:
        return None
    top_str = ", ".join(_quote(v) for v, _ in tops[:2])
    metric = snapshot.metric_columns[0] if snapshot.metric_columns else None
    temporal = f" en {snapshot.temporal_hint}" if snapshot.temporal_hint else ""

    if domain == "finance" or "facturación" in snapshot.vocabulary or "contabilidad" in snapshot.vocabulary:
        metric_part = f" («{metric}»)" if metric else ""
        return f"Ej.: Desvíos{temporal} en «{seg_col}» como {top_str}{metric_part}."
    if domain == "generic" and snapshot.vocabulary:
        theme = snapshot.vocabulary[0]
        metric_part = f"«{metric}»" if metric else "la métrica clave"
        return f"Ej.: {metric_part} elevado en {top_str} — revisar causa en contexto de {theme}."
    if metric:
        return f"Ej.: «{metric}» concentrado en {top_str} (dimensión «{seg_col}»)."
    return f"Ej.: Concentración en {top_str} por «{seg_col}»."


def build_hypothesis_example(domain: Domain, snapshot: DatasetSnapshot) -> str:
    """Hint Q2: ejemplo concreto con peor grupo detectado."""
    if domain == "healthcare_clinic" and snapshot.notable_contrast:
        return f"Ej.: {snapshot.notable_contrast}."

    contrast = snapshot.notable_contrast
    if not contrast:
        from_tops = _fallback_hypothesis_from_tops(snapshot, domain)
        if from_tops:
            return from_tops
        return _FALLBACK_HYPOTHESIS[domain]

    if domain == "healthcare_mart":
        return f"Ej.: «No-shows altos en {contrast} por falta de recordatorio»."

    if domain == "finance":
        temporal = f" en {snapshot.temporal_hint}" if snapshot.temporal_hint else ""
        return f"Ej.: Desvíos{temporal}: {contrast}."

    if domain == "operations":
        return f"Ej.: {contrast} — posible desgaste o falta de capacitación."

    vocab = snapshot.vocabulary
    theme = vocab[0] if vocab else "métrica"
    if "tecnología" in vocab or "tickets" in vocab:
        seg = snapshot.segment_columns[0] if snapshot.segment_columns else "segmento"
        tops = snapshot.top_values.get(seg, ())
        top_vals = " / ".join(_quote(v) for v, _ in tops[:2]) if tops else contrast
        metric = snapshot.metric_columns[0] if snapshot.metric_columns else "métrica"
        return f"Ej.: «{metric} elevado en {top_vals} ({theme}) — {contrast}»."
    if "facturación" in vocab or "contabilidad" in vocab:
        temporal = f" o en {snapshot.temporal_hint}" if snapshot.temporal_hint else ""
        return f"Ej.: «Desvíos en clientes como {contrast}{temporal}»."
    metric = snapshot.metric_columns[0] if snapshot.metric_columns else "métrica"
    seg = snapshot.segment_columns[0] if snapshot.segment_columns else "segmento"
    return f"Ej.: «{metric} problemático en {seg}: {contrast}»."


def build_segment_hint(snapshot: DatasetSnapshot, segment_col: str, domain: Domain) -> str:
    """Hint Q3: top valores reales de la columna de segmento."""
    tops = snapshot.top_values.get(segment_col, ())
    if tops:
        parts = ", ".join(f"{_quote(v)} ({pct:.0f}%)" for v, pct in tops[:3])
        return f"En «{segment_col}» destacan: {parts}."
    if domain == "finance":
        return "Centro de costo, cuenta contable u otra dimensión clave del desvío."
    if domain == "healthcare_clinic":
        return "Elegí la dimensión donde esperás encontrar la concentración del problema."
    if domain == "healthcare_mart":
        return "Ej.: especialidad, proveedor, canal de reserva o cobertura."
    if domain == "operations":
        return "Elegí la dimensión donde validarías primero tu hipótesis."
    if snapshot.vocabulary:
        return f"Segmentos relevantes para {snapshot.vocabulary[0]}: elegí la dimensión más sospechosa."
    return "Dimensión categórica para contrastar tu hipótesis contra los datos."


def _empty_segment_placeholder(domain: Domain) -> tuple[str, ...]:
    if domain == "generic":
        return ("— sin categóricas —",)
    return ("— sin segmentos categóricos —",)


def build_dataset_snapshot(
    df: pd.DataFrame,
    logical_types: dict[str, str],
    profile: Any,
    domain: Domain,
    findings: list | None = None,
) -> DatasetSnapshot:
    """Construye contexto ligero del dataset para preguntas y recomendaciones."""
    del profile, findings  # reservado para extensiones futuras

    if df is None or df.empty:
        return DatasetSnapshot(
            metric_columns=(),
            segment_columns=_empty_segment_placeholder(domain),
            top_values={},
            outlier_columns=(),
            compare_pair=None,
            notable_contrast=None,
            vocabulary=extract_column_vocabulary([]),
        )

    segment_columns = _rank_segment_columns(df, logical_types, domain)
    if not segment_columns:
        nums = _rank_metric_columns(df, logical_types, domain)
        segment_columns = tuple(nums[:5]) if nums else _empty_segment_placeholder(domain)

    metric_columns = _rank_metric_columns(df, logical_types, domain)

    top_values: dict[str, tuple[tuple[str, float], ...]] = {}
    for col in segment_columns:
        if col.startswith("—"):
            continue
        if col in df.columns:
            if logical_types.get(col) == "datetime":
                series = pd.to_datetime(df[col], errors="coerce").dropna().astype(str)
                if not series.empty and 2 <= int(series.nunique()) <= 50:
                    vc = series.value_counts()
                    total = float(len(series))
                    top_values[col] = tuple(
                        (str(k), float(v) / total * 100.0) for k, v in vc.head(3).items()
                    )
                    continue
            tops = _top_categorical_values(df, col)
            if tops:
                top_values[col] = tops

    outlier_findings, outlier_cols = insights_detect_outliers(df, logical_types)
    del outlier_findings
    outlier_columns = tuple(outlier_cols[:3])

    compare_pair = insights_pick_compare_pair(df, logical_types)
    notable_contrast = _detect_notable_contrast(df, logical_types, domain, compare_pair)
    vocabulary = extract_column_vocabulary(list(df.columns))
    temporal_hint = _temporal_hint(df, logical_types)

    return DatasetSnapshot(
        metric_columns=metric_columns,
        segment_columns=segment_columns,
        top_values=top_values,
        outlier_columns=outlier_columns,
        compare_pair=compare_pair,
        notable_contrast=notable_contrast,
        vocabulary=vocabulary,
        temporal_hint=temporal_hint,
    )

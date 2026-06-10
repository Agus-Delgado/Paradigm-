"""Verificación rápida de preguntas dinámicas."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from app.conversational.analysis import run_contextual_analysis
from app.conversational.domain import detect_domain
from app.conversational.legacy_bridge import build_findings, build_profile, infer_logical_types, load_csv_path, DEMO_CLINIC_CSV
from app.conversational.questions import generate_guided_questions
from app.conversational.synthetic import generate_synthetic_dataset
from app.conversational.types import DatasetContext


def prepare_ctx(df, source_label):
    logical_types = infer_logical_types(df)
    profile = build_profile(df, logical_types)
    findings = build_findings(df, profile, logical_types)
    domain = detect_domain(df, logical_types)
    return DatasetContext(
        df=df,
        logical_types=logical_types,
        profile=profile,
        findings=findings,
        domain=domain,
        dataset_key=f"test_{source_label}",
        source_label=source_label,
    )


def check(label, ctx):
    qs = generate_guided_questions(
        ctx.df,
        ctx.logical_types,
        ctx.domain,
        profile=ctx.profile,
        findings=ctx.findings,
    )
    hyp = qs[1].hint
    seg = qs[2]
    print(f"=== {label} ({ctx.domain}) ===")
    print("Q2:", hyp[:200])
    print("Q3 options:", seg.options[:4])
    print("Q3 hint:", seg.hint[:200])
    result = run_contextual_analysis(
        ctx.df,
        ctx.logical_types,
        ctx.profile,
        ctx.findings,
        {"objective": "test", "hypothesis": "", "segment_col": seg.default},
        ctx.domain,
    )
    if result.recommendations:
        print("Rec top:", result.recommendations[0].text[:180])
    print()


def main():
    df, _ = load_csv_path(DEMO_CLINIC_CSV)
    ctx = prepare_ctx(df, "demo")
    check("Demo consultorio", ctx)
    q2 = generate_guided_questions(
        ctx.df, ctx.logical_types, ctx.domain, profile=ctx.profile, findings=ctx.findings
    )[1].hint
    q3_hint = generate_guided_questions(
        ctx.df, ctx.logical_types, ctx.domain, profile=ctx.profile, findings=ctx.findings
    )[2].hint
    assert "cardiolog" in q3_hint.lower(), q3_hint
    assert "ausente" in q2.lower() and "canal" in q2.lower(), q2

    fin = generate_synthetic_dataset("finance")
    check("Sintetico finance", prepare_ctx(fin, "fin"))

    ops = generate_synthetic_dataset("operations")
    check("Sintetico operations", prepare_ctx(ops, "ops"))

    billing = pd.DataFrame(
        [
            {"cliente": "EmpresaX", "periodo": "2024-Q4", "monto_factura": 120000, "costo": 95000, "desvio_pct": 12.5},
            {"cliente": "EmpresaX", "periodo": "2024-Q4", "monto_factura": 118000, "costo": 98000, "desvio_pct": 18.2},
            {"cliente": "EmpresaY", "periodo": "2024-Q3", "monto_factura": 80000, "costo": 70000, "desvio_pct": 5.1},
            {"cliente": "EmpresaZ", "periodo": "2024-Q4", "monto_factura": 200000, "costo": 150000, "desvio_pct": 22.0},
            {"cliente": "EmpresaZ", "periodo": "2024-Q4", "monto_factura": 210000, "costo": 155000, "desvio_pct": 25.5},
            {"cliente": "EmpresaY", "periodo": "2024-Q4", "monto_factura": 85000, "costo": 72000, "desvio_pct": 8.0},
            {"cliente": "EmpresaX", "periodo": "2024-Q3", "monto_factura": 115000, "costo": 94000, "desvio_pct": 11.0},
            {"cliente": "EmpresaZ", "periodo": "2024-Q3", "monto_factura": 195000, "costo": 148000, "desvio_pct": 19.0},
        ]
    )
    ctx_b = prepare_ctx(billing, "billing")
    check("CSV facturacion", ctx_b)
    hyp_b = generate_guided_questions(
        ctx_b.df, ctx_b.logical_types, ctx_b.domain, profile=ctx_b.profile, findings=ctx_b.findings
    )[1].hint
    assert any(k in hyp_b.lower() for k in ("cliente", "empresa", "desvio", "monto")), hyp_b

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()

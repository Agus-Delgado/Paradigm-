"""
Referencia numérica de KPIs del mart (SQLite) para validar el tablero Power BI.
Ejecutar después de build_sqlite_mart; comparar con tarjetas en el lienzo.

Uso:
    python scripts/validate_executive_kpis.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "processed" / "paradigm_mart.db"


def main() -> None:
    if not DB.is_file():
        raise SystemExit(f"No existe {DB}")
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        print("=== Referencia ejecutiva (mart completo, sin filtros de fecha) ===\n")
        row = c.execute(
            """
            SELECT
              COUNT(*) AS citas_total,
              SUM(CASE WHEN status_code='ATTENDED' THEN 1 ELSE 0 END) AS attended,
              SUM(CASE WHEN status_code='CANCELLED' THEN 1 ELSE 0 END) AS cancelled,
              SUM(CASE WHEN status_code='NO_SHOW' THEN 1 ELSE 0 END) AS noshow
            FROM vw_appointment_base
            """
        ).fetchone()
        assert row is not None
        attended, cancelled, noshow = row["attended"], row["cancelled"], row["noshow"]
        denom = attended + noshow
        ns_rate = (noshow / denom) if denom else None
        can_rate = (cancelled / row["citas_total"]) if row["citas_total"] else None
        print(f"Citas Total (agenda):     {row['citas_total']}")
        print(f"Citas Atendidas:           {attended}")
        print(f"Citas Canceladas:          {cancelled}")
        print(f"Citas No-show:             {noshow}")
        print(f"No-show rate:              {ns_rate:.4f}" if ns_rate is not None else "No-show rate:              n/a")
        print(f"Tasa cancelación:          {can_rate:.4f}" if can_rate is not None else "Tasa cancelación:          n/a")

        rev = c.execute(
            """
            SELECT ROUND(SUM(CASE WHEN bs.status_code != 'VOID' THEN f.line_amount ELSE 0 END), 2)
            FROM fact_billing_line f
            JOIN dim_billing_status bs ON f.billing_status_id = bs.billing_status_id
            """
        ).fetchone()
        print(f"\nIngreso facturado (total, no VOID): {rev[0]}")

        gap = c.execute(
            """
            SELECT COUNT(*) FROM vw_revenue_bridge
            WHERE reconciliation_bucket = 'ATTENDED_NO_BILLING'
            """
        ).fetchone()[0]
        print(f"Citas atendidas sin facturación (brecha): {gap}")
    finally:
        c.close()


if __name__ == "__main__":
    main()

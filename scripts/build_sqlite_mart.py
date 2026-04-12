"""
Construye la base SQLite local del mart Paradigm v2 a partir de data/synthetic/*.csv.

Uso (desde la raíz del repo):
    python scripts/build_sqlite_mart.py

Salida: data/processed/paradigm_mart.db
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "data" / "synthetic"
DDL_PATH = ROOT / "sql" / "ddl" / "01_create_tables.sql"
VIEWS_DIR = ROOT / "sql" / "views"
OUTPUT_DB = ROOT / "data" / "processed" / "paradigm_mart.db"

# Orden respeta FKs
LOAD_ORDER: list[tuple[str, str]] = [
    ("dim_date", "dim_date.csv"),
    ("dim_specialty", "dim_specialty.csv"),
    ("dim_coverage", "dim_coverage.csv"),
    ("dim_appointment_status", "dim_appointment_status.csv"),
    ("dim_booking_channel", "dim_booking_channel.csv"),
    ("dim_billing_status", "dim_billing_status.csv"),
    ("dim_cancellation_reason", "dim_cancellation_reason.csv"),
    ("dim_patient", "dim_patient.csv"),
    ("dim_provider", "dim_provider.csv"),
    ("fact_appointment", "fact_appointment.csv"),
    ("fact_billing_line", "fact_billing_line.csv"),
]


def _prepare_dataframe(table: str, df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if table == "fact_appointment":
        for col in ("cancellation_ts",):
            if col in df.columns:
                df[col] = df[col].replace("", pd.NA)
        if "cancellation_reason_id" in df.columns:
            df["cancellation_reason_id"] = pd.to_numeric(df["cancellation_reason_id"], errors="coerce")
            df["cancellation_reason_id"] = df["cancellation_reason_id"].astype("Int64")
    return df


def main() -> None:
    if not SYNTHETIC.is_dir():
        raise SystemExit(f"No existe {SYNTHETIC}; generá primero data/synthetic con generate_paradigm_v2_synthetic.py")

    OUTPUT_DB.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_DB.exists():
        OUTPUT_DB.unlink()

    ddl_sql = DDL_PATH.read_text(encoding="utf-8")
    view_files: list[Path] = []

    conn = sqlite3.connect(OUTPUT_DB)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(ddl_sql)

        for table, csv_name in LOAD_ORDER:
            path = SYNTHETIC / csv_name
            if not path.exists():
                raise FileNotFoundError(path)
            df = pd.read_csv(path, na_values=["", "NA"])
            df = _prepare_dataframe(table, df)
            df.to_sql(table, conn, if_exists="append", index=False)

        view_files = sorted(VIEWS_DIR.glob("*.sql"))
        if not view_files:
            raise SystemExit(f"No hay vistas en {VIEWS_DIR}")
        for vf in view_files:
            conn.executescript(vf.read_text(encoding="utf-8"))

        conn.commit()
    finally:
        conn.close()

    print(f"Base creada: {OUTPUT_DB}")
    print(f"Vistas aplicadas: {len(view_files)} archivo(s)")


if __name__ == "__main__":
    main()

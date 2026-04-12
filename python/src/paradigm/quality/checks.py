"""
Checks de calidad sobre el mart SQLite (alineados a docs/data_dictionary.md).

Los WARN refieren reglas de negocio donde el sintético puede tener brechas intencionales
(p. ej. atendidas sin facturación).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from paradigm.quality.results import CheckResult, Severity


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    if row is None:
        return 0
    return int(row[0])


def check_pragma_integrity(conn: sqlite3.Connection) -> CheckResult:
    """PRAGMA integrity_check debe devolver 'ok'."""
    row = conn.execute("PRAGMA integrity_check").fetchone()
    ok = row is not None and row[0] == "ok"
    return CheckResult(
        check_id="pragma_integrity",
        name="PRAGMA integrity_check",
        severity=Severity.OK if ok else Severity.FAIL,
        detail="ok" if ok else str(row),
    )


def check_pragma_foreign_keys(conn: sqlite3.Connection) -> CheckResult:
    """PRAGMA foreign_key_check — lista vacía si no hay violaciones."""
    rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    n = len(rows)
    return CheckResult(
        check_id="pragma_foreign_key_check",
        name="PRAGMA foreign_key_check",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Sin violaciones de FK" if n == 0 else f"Violaciones: {n}",
        metric_value=n,
    )


def check_unique_appointment_ids(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM (
      SELECT appointment_id FROM fact_appointment
      GROUP BY appointment_id HAVING COUNT(*) > 1
    )
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="unique_fact_appointment",
        name="Claves únicas fact_appointment.appointment_id",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Sin duplicados" if n == 0 else f"Grupos duplicados: {n}",
        metric_value=n,
    )


def check_unique_billing_line_ids(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM (
      SELECT billing_line_id FROM fact_billing_line
      GROUP BY billing_line_id HAVING COUNT(*) > 1
    )
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="unique_fact_billing",
        name="Claves únicas fact_billing_line.billing_line_id",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Sin duplicados" if n == 0 else f"Grupos duplicados: {n}",
        metric_value=n,
    )


def check_critical_nulls_appointment(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM fact_appointment
    WHERE appointment_id IS NULL OR patient_id IS NULL OR provider_id IS NULL
       OR specialty_id IS NULL OR coverage_id IS NULL OR appointment_status_id IS NULL
       OR booking_channel_id IS NULL OR appointment_date IS NULL OR appointment_start IS NULL
       OR booking_date IS NULL OR booking_ts IS NULL
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="nulls_fact_appointment",
        name="Nulos en columnas obligatorias (fact_appointment)",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Ninguno" if n == 0 else f"Filas con nulos críticos: {n}",
        metric_value=n,
    )


def check_critical_nulls_billing(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM fact_billing_line
    WHERE billing_line_id IS NULL OR billing_date IS NULL OR line_amount IS NULL
       OR billing_status_id IS NULL OR currency IS NULL
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="nulls_fact_billing",
        name="Nulos en columnas obligatorias (fact_billing_line)",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Ninguno" if n == 0 else f"Filas con nulos críticos: {n}",
        metric_value=n,
    )


def check_booking_before_appointment(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM fact_appointment
    WHERE date(booking_date) > date(appointment_date)
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="dates_booking_le_appointment",
        name="booking_date <= appointment_date",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Cumple" if n == 0 else f"Violaciones: {n}",
        metric_value=n,
    )


def check_cancellation_consistency(conn: sqlite3.Connection) -> CheckResult:
    """Cancelada => cancellation_ts no nulo; atendida/no-show => sin cancelación."""
    sql_bad_cancel = """
    SELECT COUNT(*) FROM fact_appointment fa
    JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
    WHERE st.status_code = 'CANCELLED'
      AND (fa.cancellation_ts IS NULL OR trim(COALESCE(fa.cancellation_ts, '')) = '')
    """
    sql_bad_other = """
    SELECT COUNT(*) FROM fact_appointment fa
    JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
    WHERE st.status_code IN ('ATTENDED', 'NO_SHOW')
      AND fa.cancellation_ts IS NOT NULL AND trim(fa.cancellation_ts) != ''
    """
    n1 = _scalar(conn, sql_bad_cancel)
    n2 = _scalar(conn, sql_bad_other)
    n = n1 + n2
    return CheckResult(
        check_id="state_cancellation_ts",
        name="Consistencia estado vs cancellation_ts",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail=f"Canceladas sin ts: {n1}; otras con ts: {n2}",
        metric_value=n,
    )


def check_cancellation_reason_only_when_cancelled(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM fact_appointment fa
    JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
    WHERE st.status_code != 'CANCELLED' AND fa.cancellation_reason_id IS NOT NULL
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="cancellation_reason_only_cancelled",
        name="cancellation_reason_id solo si estado cancelada",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Cumple" if n == 0 else f"Violaciones: {n}",
        metric_value=n,
    )


def check_line_amounts_non_negative(conn: sqlite3.Connection) -> CheckResult:
    sql = "SELECT COUNT(*) FROM fact_billing_line WHERE line_amount < 0"
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="amounts_non_negative",
        name="Montos line_amount >= 0",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Cumple" if n == 0 else f"Negativos: {n}",
        metric_value=n,
    )


def check_currency_ars(conn: sqlite3.Connection) -> CheckResult:
    sql = "SELECT COUNT(*) FROM fact_billing_line WHERE currency != 'ARS'"
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="currency_ars",
        name="Moneda ARS en líneas de facturación",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Todas ARS" if n == 0 else f"Diferentes: {n}",
        metric_value=n,
    )


def check_billing_appointment_fk(conn: sqlite3.Connection) -> CheckResult:
    """Líneas con appointment_id inexistente (MVP: se espera 0)."""
    sql = """
    SELECT COUNT(*) FROM fact_billing_line f
    WHERE f.appointment_id IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM fact_appointment a WHERE a.appointment_id = f.appointment_id
      )
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="billing_fk_appointment",
        name="fact_billing_line.appointment_id existe en fact_appointment",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Sin huérfanos" if n == 0 else f"Líneas huérfanas: {n}",
        metric_value=n,
    )


def check_appointment_dates_in_dim_date(conn: sqlite3.Connection) -> CheckResult:
    sql = """
    SELECT COUNT(*) FROM fact_appointment fa
    WHERE NOT EXISTS (SELECT 1 FROM dim_date d WHERE d.date = fa.appointment_date)
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="appointment_date_in_dim_date",
        name="appointment_date presente en dim_date",
        severity=Severity.OK if n == 0 else Severity.FAIL,
        detail="Todas enlazadas" if n == 0 else f"Sin dim_date: {n}",
        metric_value=n,
    )


def check_attended_without_billing_warn(conn: sqlite3.Connection) -> CheckResult:
    """
    Atendidas sin ninguna línea de facturación: en el sintético hay brechas deliberadas (~6%).
    WARN si > 0 (informativo), no FAIL.
    """
    sql = """
    SELECT COUNT(*) FROM fact_appointment fa
    JOIN dim_appointment_status st ON fa.appointment_status_id = st.appointment_status_id
    WHERE st.status_code = 'ATTENDED'
      AND NOT EXISTS (
        SELECT 1 FROM fact_billing_line f WHERE f.appointment_id = fa.appointment_id
      )
    """
    n = _scalar(conn, sql)
    return CheckResult(
        check_id="attended_without_billing",
        name="Citas atendidas sin línea de facturación (brecha operativa)",
        severity=Severity.WARN if n > 0 else Severity.OK,
        detail=(
            "Ninguna brecha"
            if n == 0
            else f"Cantidad: {n} (esperado en sintético para demo de conciliación)"
        ),
        metric_value=n,
    )


ALL_CHECKS: list[Callable[[sqlite3.Connection], CheckResult]] = [
    check_pragma_integrity,
    check_pragma_foreign_keys,
    check_unique_appointment_ids,
    check_unique_billing_line_ids,
    check_critical_nulls_appointment,
    check_critical_nulls_billing,
    check_booking_before_appointment,
    check_cancellation_consistency,
    check_cancellation_reason_only_when_cancelled,
    check_line_amounts_non_negative,
    check_currency_ars,
    check_billing_appointment_fk,
    check_appointment_dates_in_dim_date,
    check_attended_without_billing_warn,
]

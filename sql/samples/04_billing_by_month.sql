-- Facturación por mes (anclaje: billing_date; excluye líneas VOID)
SELECT
  strftime('%Y-%m', fbl.billing_date) AS billing_month,
  ROUND(SUM(CASE WHEN bs.status_code != 'VOID' THEN fbl.line_amount ELSE 0 END), 2) AS ingreso_facturado
FROM fact_billing_line fbl
JOIN dim_billing_status bs ON fbl.billing_status_id = bs.billing_status_id
GROUP BY strftime('%Y-%m', fbl.billing_date)
ORDER BY billing_month;

-- Conciliación atención vs facturación: resumen por bucket (vw_revenue_bridge)
SELECT
  reconciliation_bucket,
  COUNT(*) AS citas,
  ROUND(SUM(revenue_total_non_void), 2) AS ingreso_no_void
FROM vw_revenue_bridge
GROUP BY reconciliation_bucket
ORDER BY citas DESC;

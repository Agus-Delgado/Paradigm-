# Evidencia de portfolio — dónde va cada cosa

Este archivo indica **qué** mostrar en GitHub o en una entrevista y **dónde** vive en el repo. Las capturas de BI son **opcionales** hasta que las generés en Desktop.

## Reportes y métricas regenerables

| Artefacto | Ruta | Notas |
|-----------|------|--------|
| Reporte de calidad del mart | [`reports/quality_report.md`](../reports/quality_report.md) | Ejecutar `python scripts/run_data_quality.py` después del build |
| Métricas del modelo ML | [`ml/experiments/metrics.json`](../ml/experiments/metrics.json) | Ejecutar `python scripts/train_no_show.py`; **no** interpretar el puntaje como éxito de negocio en datos sintéticos |

## Capturas sugeridas (placeholders)

Colocar imágenes **PNG o WebP** en [`../assets/bi/`](../assets/README.md) con nombres consistentes:

| Vista | Archivo sugerido | Contenido mínimo |
|-------|------------------|------------------|
| Power BI — ejecutivo | `powerbi_executive.png` | Barra de filtros + KPIs + una tendencia (sin datos sensibles) |
| Tableau — analítico | `tableau_analytics.png` | Una heatmap o vista de causa; coherente con `bi/tableau/README.md` |

Hasta que existan archivos reales, el [`README.md`](../README.md) raíz enlaza esta carpeta sin asumir que ya hay imágenes.

## Enlace en el README raíz

El README principal resume esta tabla en la sección **Evidencia de portfolio** y apunta aquí para el detalle.

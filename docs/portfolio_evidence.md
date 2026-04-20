# Evidencia de portfolio — dónde va cada cosa

Este archivo indica **qué** mostrar en GitHub o en una entrevista y **dónde** vive en el repo, alineado a la narrativa de **inteligencia operativa aplicada**. Las capturas de BI en `assets/bi/` son **opcionales** hasta que las generés en Desktop; no hace falta commitear imágenes nuevas para que el repo sea coherente.

**Guion y orden de demo en pantalla:** [`portfolio_presentation.md`](portfolio_presentation.md).

---

## Convención de rutas: `public/img` vs `assets/bi`

| Ubicación | Rol | Archivo ejecutivo Power BI |
|-----------|-----|----------------------------|
| [`public/img/Dashboard_ejecutivo.png`](../public/img/Dashboard_ejecutivo.png) | **Ejemplo fijo** referenciado por el README raíz; conviene mantenerlo para que la landing del repo muestre siempre una vista ejecutiva. | `Dashboard_ejecutivo.png` |
| `assets/bi/powerbi_executive.png` ([convención](../assets/README.md)) | **Opcional:** misma idea de vista ejecutiva con **nombre unificado** para portfolio o GitHub si preferís centralizar capturas en `assets/bi/`. El archivo PNG se añade cuando lo generés; el enlace va a la convención para evitar rutas rotas en GitHub. | `powerbi_executive.png` |

Podés **copiar** la misma captura a `assets/bi/powerbi_executive.png` cuando la tengas, o dejar solo `public/img/`. No dupliques narrativas: en demo, mostrá **una** vista ejecutiva primero (orden abajo).

**Tableau** no tiene imagen fija en `public/img/`; la convención es `assets/bi/tableau_analytics.png` cuando exista ([misma convención](../assets/README.md)).

---

## Orden recomendado de revelación (demo o README)

1. **Vista ejecutiva (Power BI)** — “qué pasó en el periodo” en pocas señales (`Dashboard_ejecutivo.png` o `powerbi_executive.png`).
2. **Vista analítica (Tableau)** — cortes, causa, segundo lente (`tableau_analytics.png` cuando exista).
3. **Respaldo técnico** — [`reports/quality_report.md`](../reports/quality_report.md) y/o [`ml/experiments/metrics.json`](../ml/experiments/metrics.json) para credibilidad de pipeline y ML, no como primera pantalla.

Si **aún no** tenés captura en `assets/bi/`, el README sigue mostrando el ejecutivo desde `public/img/`; mencioná Tableau por la guía en [`bi/tableau/README.md`](../bi/tableau/README.md) sin inventar una imagen.

---

## Reportes y métricas regenerables

| Artefacto | Ruta | Notas |
|-----------|------|-------|
| Reporte de calidad del mart | [`reports/quality_report.md`](../reports/quality_report.md) | Ejecutar `python scripts/run_data_quality.py` después del build |
| Métricas del modelo ML | [`ml/experiments/metrics.json`](../ml/experiments/metrics.json) | Ejecutar `python scripts/train_no_show.py`; **no** interpretar el puntaje como éxito de negocio en datos sintéticos |

---

## Capturas sugeridas (`assets/bi/`)

Colocar imágenes **PNG o WebP** en [`../assets/bi/`](../assets/bi/) con estos nombres (alineados a [`assets/README.md`](../assets/README.md) y al README raíz):

| Vista | Archivo | Contenido mínimo |
|-------|---------|-------------------|
| Power BI — ejecutivo | `powerbi_executive.png` | Barra de filtros + KPIs + una tendencia (sin datos sensibles) |
| Tableau — analítico | `tableau_analytics.png` | Una heatmap o vista de causa; coherente con [`bi/tableau/README.md`](../bi/tableau/README.md) |

---

## Checklist antes de una demo o entrevista

- [ ] Pipeline corrido al menos hasta mart + calidad: `build_sqlite_mart.py`, `run_data_quality.py` (y exports BI si vas a abrir Desktop).
- [ ] `reports/quality_report.md` presente o regenerado.
- [ ] `ml/experiments/metrics.json` alineado al último entrenamiento si hablás de ML.
- [ ] Saber qué imagen usás para ejecutivo: `public/img/Dashboard_ejecutivo.png` y/o `assets/bi/powerbi_executive.png`.
- [ ] Tener claro el orden **1 → 2 → 3** de la sección “Orden recomendado” arriba.

---

## Enlace en el README raíz

El README principal resume la tabla de evidencia en la sección **Demo, evidencia y entregables** y apunta aquí para convención de rutas y detalle.

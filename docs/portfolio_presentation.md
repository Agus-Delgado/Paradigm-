# Cómo presentar Paradigm v2 (demo / entrevista)

Guía breve para **30–60 segundos** de pitch y un recorrido de **5–10 minutos** si piden profundidad.

---

## Pitch 30–60 segundos

> Paradigm v2 es un proyecto de portfolio de **analítica operativa ambulatoria**: generé un **dataset sintético dimensional**, lo modelé en **SQL** con un mart SQLite, definí **KPIs documentados**, validé con **checks de calidad** en Python, y preparé **dos capas de BI** — Power BI para el ejecutivo y Tableau para el análisis — más un **modelo de ML** de riesgo de no-show como capa complementaria. Todo es **reproducible desde scripts** y los datos son ficticios; el foco está en **criterio de diseño y gobernanza**, no en fingir resultados de un hospital real.

Ajustá el tono a la oferta (más BI, más datos, más ML).

---

## Qué mostrar primero (orden sugerido)

1. **README del repo** o una slide con el diagrama (datos → mart → calidad → BI / ML).
2. **`docs/metric_definitions.md`** o una captura: demostrás que las métricas tienen **numerador, denominador y anclaje temporal**.
3. **`reports/quality_report.md`** (o fragmento): trazabilidad entre “datos cargados” y “listo para consumir”.
4. **Power BI** (captura o `.pbix` local): **una pantalla ejecutiva** — decís que el repo trae CSV + DAX + instrucciones.
5. **Tableau** (captura): **una vista analítica** distinta (exploración / causa), sin duplicar el ejecutivo.
6. **ML** (`ml/README.md` + `metrics.json`): enfatizá **punto de decisión, split temporal y leakage**, no el AUC como victoria comercial.

Si el tiempo aprieta: puntos **1 → 2 → 4** y cerrás con limitaciones honestas.

---

## Decisiones técnicas a defender

| Decisión | Por qué |
|----------|---------|
| **SQLite** para el mart | Portabilidad, un archivo, suficiente para MVP y portfolio; no necesitás un warehouse para demostrar SQL. |
| **KPIs en documento + SQL** | Los tableros heredan definiciones; se evita “cada visual con su fórmula”. |
| **Power BI vs Tableau** | Ejecutivo = pocas métricas y tendencia; analítico = cortes y causa — roles distintos, mismo mart. |
| **Split temporal en ML** | Evita mezclar futuro y pasado en validación; coherente con despliegue real. |
| **Datos sintéticos** | Ética y claridad; el valor es el **método**, no una predicción productiva. |

---

## Limitaciones a mencionar con honestidad

- Los datos **no** son reales; cualquier cifra es **ilustrativa**.
- Los **.pbix / .twbx** no están versionados como binarios por defecto; el entregable es **material + documentación** para armarlos.
- El **ML** puede tener **bajo poder predictivo** en sintético; lo defendible es la **definición del problema, features y evaluación**, no un lift operativo inventado.
- **Ocupación** y **ingreso cobrado** estricto están **acotados o fuera** del MVP según `metric_definitions.md`.

---

## Preguntas que pueden aparecer

- **¿Por qué dos herramientas de BI?** Misma fuente, roles distintos; evitás un tablero que intenta ser ejecutivo y forense a la vez.
- **¿Cómo validás KPIs?** Script de validación ejecutiva + alineación al diccionario + calidad en el mart.
- **¿El modelo ML está en producción?** No; es una **capa de demostración** y priorización conceptual.

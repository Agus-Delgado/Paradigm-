# Auditoría de reproducibilidad — No-Show

**Fecha:** 2026-07-21
**Alcance:** pipeline `paradigm.ml.train` / `scripts/train_no_show.py` sobre el mismo mart y entorno.
**Entorno auditado:** Python 3.13.12 · pandas 3.0.3 · NumPy 2.4.6 · scikit-learn 1.9.0.

## Resumen ejecutivo

La construcción del dataset, las features, el split, los modelos entrenados, las clases
predichas y las métricas de ranking son reproducibles en el entorno auditado.

La variación observada quedó aislada en `RandomForestClassifier.predict_proba`:
con `n_jobs=-1`, scikit-learn agrega en paralelo las probabilidades de los árboles.
El orden de acumulación puede variar y cambia el último bit del resultado
(`1.11e-16` a `2.22e-16`). Eso:

- cambia el SHA-256 de las probabilidades y del CSV;
- puede cambiar el último decimal del Brier score;
- **no** cambió clases predichas, ROC-AUC, AP, top-decile ni el modelo serializado.

`n_jobs=-1` era responsable de la variación **bit a bit en inferencia**, pero no
explica diferencias sustantivas históricas como ROC-AUC 0.4227 vs 0.4102. Esas
métricas provienen de artefactos ejecutados en momentos/entornos no registrados:
el `metrics.json` histórico no conserva versiones ni hashes de entrada suficientes
para atribuir esa diferencia. En tres corridas consecutivas controladas, ROC-AUC fue
0.4102272727272727 en todos los casos.

## Método

Se hicieron tres ejecuciones completas consecutivas con:

- el mismo `paradigm_mart.db`;
- el mismo proceso Python y entorno;
- output y runs en directorios temporales;
- `random_state=42`;
- los hiperparámetros actuales sin cambios.

En paralelo se capturó el núcleo previo a SHAP/serialización para comparar:
dataset, orden, features, índices, labels, probabilidades, predicciones y métricas.

## Inmutabilidad de entradas

| Artefacto | SHA-256 antes | SHA-256 después | Resultado |
|-----------|---------------|----------------|-----------|
| `data/processed/paradigm_mart.db` | `7e7d46e7bfe2304d1c0e26c58cd94322dbd7d31d11d746daeb68df0f3a6df579` | igual | Sin cambios |
| 11 CSVs de `data/synthetic/` | hashes individuales comparados | iguales | Sin cambios |

`train_no_show.py` no invoca el generador sintético ni `build_sqlite_mart.py`.
Solo lee el mart y escribe modelos, métricas, predicciones, SHAP y el nuevo run.

## Hashes previos al entrenamiento

Los tres runs produjeron exactamente estos hashes:

| Objeto | Filas | SHA-256 |
|--------|------:|---------|
| Dataset con features, previo al split | 423 | `c1d11803cc9c44b6b1a7d7e3c3f036d6adca14bdacaced1bbb2f286710acd6aa` |
| `X_train` | 332 | `e6c0e5daddd05c6da26266245465bb5638fe5046f0faa7b44366f918be67139f` |
| `X_test` | 91 | `ebd67d30734d7d9fb28c96b671036a82a72724f59d76af6258c105332aeba36f` |
| `y_train` | 332 | `0ab76fee5194f094bc3dd9852f6c2c159fd3c40fa9a747291f578e5d738405eb` |
| `y_test` | 91 | `3ea58269b05aeb7105d4707b525a062fba7771d453dda9febad80ebc9dedd3ae` |

También fueron idénticos:

- orden de citas: `4bc6ae8b119115fc3ff63dbf9cc1d70aaa6095dbb98e95ad4f3b1b2d9d60c24c`;
- índices train: `05f40c0535ca7ed3bcd1bc085b5d023a8178855b33c595ea77939a9995a32e7a`;
- índices test: `92896e789b377119f18646c23c6bba2fbcfc5437a25e3d8676940492898e600c`;
- cutoff: `2024-12-05`;
- `y_test` (11 positivos);
- nombres y orden de las 17 columnas del frame y las 40 features transformadas.

## Comparación de tres runs — antes de la corrección

| Evidencia | Run 1 | Run 2 | Run 3 |
|-----------|-------|-------|-------|
| Dataset / X / y / orden / split | Igual | Igual | Igual |
| Logistic proba SHA-256 | `5afb…5372` | `5afb…5372` | `5afb…5372` |
| Logistic pred SHA-256 | `310c…0474` | `310c…0474` | `310c…0474` |
| RF proba SHA-256 | `2696…dead` | `32e4…8b7` | `5ad0…ee3` |
| Máx. diferencia RF vs run 1 | 0 | `1.11e-16` | `1.67e-16` |
| RF pred SHA-256 | `2fcd…4943` | `2fcd…4943` | `2fcd…4943` |
| Modelo RF joblib SHA-256 | `d734…2624` | `d734…2624` | `d734…2624` |
| RF ROC-AUC | 0.4102272727 | 0.4102272727 | 0.4102272727 |
| RF Brier | 0.17667075687531517 | 0.17667075687531514 | 0.17667075687531514 |
| Estado del run | completed | completed | completed |

Los CSV de predicciones tenían hashes distintos únicamente por los últimos bits de
`proba_random_forest`; los modelos serializados fueron idénticos.

## Confirmación de causa raíz

Sobre un único modelo RF ya entrenado se invocó `predict_proba` cinco veces:

| Modo de inferencia | Hashes únicos | Máx. diferencia |
|--------------------|--------------:|----------------:|
| `n_jobs=-1` | 5 de 5 | `2.22e-16` |
| Acumulación con un worker | 1 de 5 | `0.0` |

Esto confirma que la fuente inmediata era el orden no determinista de reducción
flotante durante inferencia paralela, no la generación de árboles. El modelo
serializado idéntico en los tres runs descarta variación del fit en este entorno.

## Corrección mínima aplicada

Se agregó `_predict_deterministically` en `paradigm.ml.train`:

1. el RF conserva `n_jobs=-1` para fit y como hiperparámetro;
2. durante `predict` / `predict_proba` se usa temporalmente un solo worker;
3. `n_jobs` se restaura inmediatamente antes de serializar o retornar el modelo.

No se modificaron features, target, split, modelos, hiperparámetros, métricas ni
criterio de selección. La corrección solo fija el orden de la reducción numérica
en inferencia.

## Comparación de tres runs — después de la corrección

| Evidencia | Run 1 | Run 2 | Run 3 |
|-----------|-------|-------|-------|
| Dataset SHA-256 | `c1d1…d6aa` | igual | igual |
| `X_train` / `X_test` / `y_train` / `y_test` | iguales | iguales | iguales |
| Logistic proba SHA-256 | `5afb…5372` | igual | igual |
| Logistic pred SHA-256 | `310c…0474` | igual | igual |
| RF proba SHA-256 | `2632…82b4` | igual | igual |
| RF pred SHA-256 | `2fcd…4943` | igual | igual |
| Máx. diferencia RF | 0 | 0 | 0 |
| Métricas completas | iguales | iguales | iguales |
| RF ROC-AUC | 0.4102272727 | 0.4102272727 | 0.4102272727 |
| RF Brier | 0.17667075687531514 | igual | igual |

## Revisión estática

| Riesgo revisado | Evidencia | Evaluación |
|-----------------|----------|------------|
| Orden implícito de SQL | `LOAD_SQL` no tiene `ORDER BY` | Riesgo restante si cambia/reconstruye el motor; estable en este mart |
| Orden histórico | `sort_values(..., kind="mergesort")` con `appointment_id` como desempate | Determinista |
| Sets/dicts de features | Features son listas explícitas; transformers tienen orden fijo | Determinista |
| Índices no reseteados | Se preservan, pero hashes/índices fueron iguales | Estable; fragilidad menor |
| Sampling | Solo fallback SHAP usa `shap.sample(..., random_state=42)` | Determinista |
| Transformaciones con estado | `StandardScaler` + `OneHotEncoder`; fit sobre X idéntica | Determinista |
| Paralelismo | RF `n_jobs=-1` | Fit idéntico; inferencia corregida |
| Artefactos previos | El pipeline no carga modelos/métricas previos; los sobrescribe | Sin contaminación |
| Métricas | Funciones puras sobre `y_test` y proba | Deterministas con proba estable |
| Selección | RF fijo como modelo seleccionado | No depende de resultados |

## Nivel de reproducibilidad actual

- **Mismo mart + mismo entorno:** alto / bit a bit para dataset, split,
  probabilidades, predicciones, métricas y joblibs cubiertos por tests.
- **Mart reconstruido:** medio-alto; los datos sintéticos tienen seed, pero la
  consulta sin `ORDER BY` deja un riesgo de orden implícito.
- **Otro entorno:** medio; `requirements.txt` usa mínimos (`>=`) y no hay lockfile.

## Fuentes de variabilidad restantes

1. `LOAD_SQL` sin `ORDER BY`: SQLite suele devolver el orden de inserción, pero no
   es contrato SQL.
2. Dependencias no fijadas: resultados pueden cambiar entre versiones de
   scikit-learn, NumPy o pandas.
3. El parámetro `random_state` de `run_training` se acepta pero hoy no se propaga;
   los builders fijan 42. No afecta esta auditoría (todas las corridas usan 42),
   pero limita la trazabilidad de seeds alternativos.
4. SHAP puede depender de versión/backend; no participa en las métricas predictivas.
5. Los artefactos históricos no registran hashes de dataset ni versiones, por lo
   que no se pueden comparar causalmente con el entorno actual.

## Recomendación

La corrección mínima ya aplicada resuelve la variación confirmada sin cambiar la
metodología. Como trabajo posterior separado: agregar `ORDER BY` explícito al load,
propagar el argumento `random_state`, y fijar el entorno con lockfile. No se aplican
esas medidas en esta auditoría porque ampliarían el alcance.

# Paradigm

Aplicación **standalone** en Python para un **análisis inicial automático** sobre tablas cargadas desde archivos CSV o Excel (primera hoja). Está orientada a perfiles de **analista de datos / BI**: exploración rápida, inferencia de tipos de columnas, perfilado básico y visualización en una interfaz web sencilla.

---

## Descripción breve

Paradigm permite subir un dataset, obtener un **resumen ejecutivo** (volumen, nulos, duplicados, memoria, distribución de tipos inferidos y una calidad estimada), revisar **hallazgos automáticos** con reglas heurísticas, explorar una **vista filtrada** con filtros en la barra lateral, vista previa flexible y **gráfico exploratorio**, y profundizar en el **perfil por columna** y en un gráfico de **nulos por columna** sobre el archivo completo. El diseño es **agnóstico al dominio** (salud, logística, ventas, deportes, etc.): no asume reglas de negocio de un sector concreto.

---

## Objetivo del proyecto

- Ofrecer una **primera pasada analítica** sobre datos tabulares sin configurar pipelines, bases de datos ni entornos complejos.
- Servir como **base standalone** que en el futuro podría integrarse en otras aplicaciones o evolucionar con nuevas capacidades, manteniendo el foco en la capa de exploración y perfilado de datos.

---

## ¿Qué hace este MVP?

Este repositorio contiene una **primera versión funcional**: una app Streamlit que carga archivos, infiere tipos lógicos de columnas, calcula un perfilado global y por columna, muestra KPIs y gráficos Plotly, y ofrece **exploración interactiva** con filtros sobre columnas elegibles y un gráfico exploratorio acorde al tipo de cada columna.

---

## Funcionalidades actuales

| Área | Detalle |
|------|--------|
| **Carga** | Archivos `.csv` y `.xlsx` desde el navegador. |
| **Excel** | Lectura de la **primera hoja** por defecto. |
| **CSV** | Intento de lectura con varios **encodings** comunes y separadores **`,`**, **`;`** y tabulador; elegir el mejor resultado según columnas detectadas. |
| **Inferencia de tipos** | Tipos lógicos internos: `numeric`, `categorical`, `boolean`, `datetime`, `text`, `id` (heurísticas con límites conocidos). En la interfaz se muestran etiquetas en español. |
| **Resumen ejecutivo** | KPIs globales: filas, columnas, % de nulos global, filas duplicadas, memoria aproximada, calidad estimada y gráfico de **columnas por tipo inferido** (sobre el dataset completo cargado). |
| **Hallazgos automáticos** | Mensajes priorizados según reglas fijas (p. ej. duplicados, nulos altos, cardinalidad), sin modelos de ML. Se calculan sobre el **archivo completo**. |
| **Exploración interactiva** | En la barra lateral: **filtros** por columnas categóricas, numéricas, booleanas o fecha (hasta 6 columnas). La **vista previa** y el **gráfico exploratorio** usan solo las filas que cumplen los filtros (**vista filtrada**). |
| **Perfil por columna** | Tabla detallada (tipos inferidos, nulos, cardinalidad, etc.) en un panel expandible; métricas referidas al dataset completo. |
| **Gráficos (dataset completo)** | Gráfico de barras de **% de nulos por columna** respecto del archivo cargado completo (independiente de los filtros de exploración). |
| **Ejemplos** | Datasets de muestra en `data/sample/` para pruebas rápidas. |

---

## Stack tecnológico

- **Python** 3.10+
- **Streamlit** — interfaz web
- **Pandas** — manipulación y perfilado tabular
- **Plotly** — gráficos interactivos
- **openpyxl** — lectura de Excel (`.xlsx`)

---

## Estructura del proyecto

```
Paradigm/
├── app/
│   ├── __init__.py
│   ├── main.py              # Punto de entrada Streamlit
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ingestion.py   # Carga CSV/XLSX
│   │   ├── schema.py      # Inferencia de tipos lógicos
│   │   ├── profiling.py   # Perfilado global y por columna
│   │   ├── exploration.py # Filtros, máscaras y tipos de gráfico exploratorio
│   │   ├── findings.py    # Hallazgos heurísticos
│   │   └── utils.py       # Utilidades compartidas
│   └── visualization/
│       ├── __init__.py
│       └── charts.py      # Figuras Plotly
├── data/
│   └── sample/            # CSV de ejemplo
├── requirements.txt
└── README.md
```

---

## Instalación

```powershell
cd ruta\a\Paradigm
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux o macOS:

```bash
cd ruta/a/Paradigm
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Cómo ejecutar la app

Desde la **raíz del repositorio** (carpeta `Paradigm`):

```powershell
streamlit run app/main.py
```

Streamlit mostrará una URL local (por defecto `http://localhost:8501`). Abrirla en el navegador.

---

## Cómo probarla con los datasets de ejemplo

1. Ejecutar la app como arriba.
2. En el panel de carga, seleccionar un archivo desde `data/sample/`:
   - `ventas_ejemplo.csv` — columnas con números, fechas y categorías.
   - `mixto.csv` — mezcla de tipos (incluye texto largo y UUIDs de ejemplo).
3. Revisar el resumen ejecutivo, hallazgos, exploración con filtros (opcional), perfil por columna y gráfico de nulos.

---

## Flujo funcional del MVP

```mermaid
flowchart LR
  A[Subir CSV o XLSX] --> B[Ingestión y lectura]
  B --> C[Inferencia de tipos por columna]
  C --> D[Perfilado global y por columna]
  D --> E[Resumen ejecutivo y hallazgos]
  E --> F[Exploración con filtros]
  F --> G[Vista previa y gráfico exploratorio]
  D --> H[Perfil por columna y gráfico de nulos global]
```

1. El usuario sube un archivo.
2. Se lee el contenido en un `DataFrame` (con manejo básico de errores y formatos).
3. Se asignan tipos lógicos por columna.
4. Se calculan métricas de perfilado y hallazgos automáticos.
5. Se muestran resumen ejecutivo (global), hallazgos, exploración filtrada (vista previa + gráfico exploratorio), tabla de perfil por columna y gráfico de nulos sobre el dataset completo.

---

## Limitaciones actuales

- **Una sola hoja** en Excel (la primera); no hay selector de hojas.
- **Inferencia heurística** de tipos: puede equivocarse en columnas ambiguas (p. ej. IDs numéricos, fechas en formatos raros).
- **Rendimiento**: pensado para datasets que caben en memoria en una máquina local; no hay procesamiento distribuido ni streaming.
- **Gráficos**: conjunto fijo y automático; no hay editor de dashboards ni personalización avanzada de gráficos.
- **Sin base de datos**, **sin autenticación** y **sin modelos de Machine Learning** en esta versión.

---

## Próximos pasos (posibles)

Estas líneas son **orientativas** y no forman parte del alcance actual del MVP:

- Refinar heurísticas de tipos y mensajes al usuario.
- Mejoras de UX (selección de hoja en Excel, límites de tamaño de archivo más explícitos).
- Tests automatizados sobre módulos de ingestión y perfilado.
- Evolución futura de la aplicación (p. ej. integración con otros sistemas) sin comprometer el alcance descrito aquí.

No se incluye en el estado actual del repositorio entrenamiento de modelos ni pipelines de ML.

---

## Capturas de pantalla

Para enriquecer el README en GitHub o en un portfolio, se pueden añadir capturas en una carpeta `docs/images/` (crearla si hace falta) y enlazarlas aquí, por ejemplo:

```markdown
![Vista principal](docs/images/paradigm-vista.png)
```

*(Sustituir por capturas reales cuando estén disponibles.)*

---

## Valor para portfolio (BI / Data Analyst)

Este proyecto muestra de forma práctica:

- **Comprensión del flujo de datos**: de archivo crudo a tabla estructurada.
- **Criterio de calidad de datos**: nulos, duplicados, cardinalidad y tipos inferidos.
- **Comunicación de resultados**: KPIs, hallazgos y visualizaciones en una interfaz accesible.
- **Stack habitual** en analítica y prototipos (Python, Pandas, visualización).

Es un ejemplo concreto de **herramienta de exploración** que puede explicarse en entrevistas técnicas sin sobredimensionar el alcance.

---

## Licencia

**Licencia no especificada aún.** El autor puede definir una licencia abierta (MIT, Apache-2.0, etc.) o restricciones de uso cuando corresponda. Hasta entonces, el uso del código queda bajo la responsabilidad de quien lo clone o modifique.

---

## Contacto / repositorio

Ajustar esta sección con el enlace al repositorio público o perfil profesional cuando se publique el proyecto.

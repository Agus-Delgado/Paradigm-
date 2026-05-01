# Paradigm — Problem and solution framing

## Outpatient operations context

Ambulatory clinics and outpatient departments schedule care in slots. When patients **do not attend without timely cancellation (no-shows)**, cancel **late**, or when **billing does not align** with services rendered, operations lose utilization, revenue, and administrative efficiency.

## Why governed metrics matter

Without **explicit KPI definitions** (numerator, denominator, and **time anchoring**), teams can compute incompatible numbers from the same raw tables. Dashboards become hard to **audit**, compare across periods, or defend in reviews. Paradigm treats **metric governance** and **dimensional clarity** as first-class—not optional polish after the visuals.

## Why synthetic data is used

All identifiers and facts in this repository are **synthetic**. They do **not** represent real patients, providers, or institutions. Synthetic data keeps the focus on **method**: modeling, definitions, reproducibility, and honest limits—without implying real-world findings.

## What Paradigm demonstrates

Paradigm shows how to:

- Structure outpatient-style operations as a **dimensional model** with clear grain.
- Implement a **repeatable pipeline** from CSV sources to a **SQLite mart** with KPI-oriented SQL views.
- Run **data-quality checks** and **script-based KPI validation** against the same mart used for BI and ML.
- Consume the mart through **documented BI patterns** (executive vs diagnostic lenses) and a **scoped ML prioritization experiment** framed as methodology, not production prediction.

For the analytical question framework (T1–T6), traceability to SQL/BI, and decision-use cases, see [`analytical_questions.md`](analytical_questions.md).

## Limitations and responsible framing

- **Illustrative numbers:** any figure derived from synthetic data is for demonstration only.
- **MVP scope:** single-site assumptions; fine-grained capacity modeling and real treasury/cash flows are out of scope unless explicitly extended.
- **Provider metrics:** operational workload metrics are **not** clinical quality judgments.
- **ML:** the no-show layer documents decision timing, leakage rules, and evaluation—not a claim of deployable predictive accuracy on synthetic signal.

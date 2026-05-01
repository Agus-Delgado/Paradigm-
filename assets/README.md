# Assets — portfolio visuals (canonical)

This folder is the **single place** for committed portfolio images referenced from the root [`README.md`](../README.md) and [`docs/portfolio.md`](../docs/portfolio.md). Paths below are from the **repository root**.

## Layout

| Subfolder | Purpose |
|-----------|---------|
| `assets/dashboards/` | BI dashboard screenshots (executive, and optionally other views) |
| `assets/diagrams/` | Static architecture or data-flow images (export from Mermaid or design tool) |
| `assets/walkthrough/` | Optional short demo GIF or storyboard frames |
| `assets/bi/` | Optional **additional** captures (e.g. Tableau) if you keep a separate naming convention |

---

## Committed assets

| Path | Type | Source / origin | Status | Notes |
|------|------|-----------------|--------|--------|
| [`dashboards/powerbi_executive.png`](dashboards/powerbi_executive.png) | Dashboard screenshot | Power BI executive canvas (synthetic data) | **Committed** | Synthetic data only; replace when the executive dashboard design changes. Regenerate by exporting a PNG from Power BI Desktop after rebuilding from `bi/powerbi/source_csv/`. |

---

## Planned (not in repo yet — do not add blank PNGs)

| Path | Type | Notes |
|------|------|--------|
| `diagrams/architecture.png` | Diagram | Optional export from [`docs/architecture.md`](../docs/architecture.md) Mermaid or equivalent |
| `diagrams/data_flow.png` | Diagram | Optional lineage / pipeline figure for README or portfolio |
| `walkthrough/demo.gif` | GIF | Optional 60–90s UI walkthrough placeholder |
| `bi/tableau_analytics.png` | Dashboard screenshot | Optional Tableau diagnostic view; add when exported — folder exists with `.gitkeep` until then |

---

## Conventions

- **Executive snapshot** for the landing README: **`assets/dashboards/powerbi_executive.png`** (canonical).
- Do not commit empty placeholder images; add `.gitkeep` only in otherwise-empty folders if needed for Git.

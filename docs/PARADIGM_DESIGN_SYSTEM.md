# Paradigm Design System — Mineral Observatory

**Lenguaje visual:** Paradigm Mineral (prototipo aprobado → app)  
**Producto:** Paradigm (no renombrar)  
**Narrativa cognitiva (Home):** `Capture → Understand → Model → Evaluate → Decide`  
**Narrativa de etapas de producto:** `Signal → Structure → Interpretation → Decision → Action`  
**Alcance:** identidad, tokens, shell y módulos migrados. No prescribe lógica de datos/ML.

---

## 1. Identidad visual

**Personalidad.** Laboratorio cognitivo mineral: preciso, tipográfico, sin glow. La UI se lee como una mesa de señales, no como un dashboard corporativo.

**Sensaciones.** Claridad, trazabilidad, quietud, jerarquía semántica.

**Evitar.** Cyan eléctrico / glow neon; navy legacy visible en shell; purple-indigo SaaS; cards repetidas sin función; pills decorativas; Inter por defecto.

---

## 2. Paleta mineral (tokens)

| Token | Hex | Uso |
|-------|-----|-----|
| `bg.main` | `#121116` | Fondo app |
| `bg.secondary` / sidebar | `#16141C` | Rail secundario |
| `surface` | `#1B1920` | Superficies |
| `text.primary` | `#F1ECE3` | Cuerpo / títulos |
| `decision` | `#D8C46A` | Decisión, activo nav, énfasis |
| `structure` / `interpretation` | `#9B8FC4` | Estructura / insight |
| `action` / `risk` | `#C9675A` | CTA primaria / riesgo |
| `signal` / `success` | `#719887` | Señal / OK |

CSS: `--pd-*` en `assets/css/custom.css`. Aliases `--cyan*` / `--bg-*` solo para consumidores legacy (landing marketing).

**Reglas.** `action` solo en CTA primaria. `risk` nunca decorativo. Nav activa usa `decision`, no coral.

---

## 3. Tipografía

IBM Plex Sans / Mono (fallbacks sistema). Uppercase + tracking solo en labels de etapa y eyebrows.

---

## 4. Shell

- **Topbar global:** marca `P` · Home · Work · Assistant · System (`paradigm_active_space` / `paradigm_active_view`).
- **Sidebar secundaria:** dataset, vistas del espacio, filtros (Home / Data & Quality), recientes, mantenimiento. `initial_sidebar_state=collapsed`.
- **Page header** (páginas internas): sección · título · propósito · etapa/estado. Notas = Capabilities / Limitations (`.pd-page-notes`).
- **Home:** composición mineral aprobada (núcleo + secuencia cognitiva + launcher + resultados). Sin marker `:has()` para el fondo.

---

## 5. Módulos migrados

| Vista | Secuencia / composición |
|-------|-------------------------|
| Assistant | `Route → Dataset → Understand → Decide` + router tipográfico + wizard mineral |
| Copilot | Intake + `Input → Analysis → Issues → Proposal → Risk` |
| Automation | `Trigger → Validate → Approve → Execute → Observe` (`.pd-auto-rail`) |
| Governance | `Risks → Decisions → Improvements` + Principles / Backlog / Limitations (`.pd-gov-*`) |
| Data & Quality | `Source → Validation → Reconciliation → Evidence` (`.pd-process-rail`) |

Chat, SQL Explorer y Data Explorer: overrides minerales tipográficos (sin cards navy/cyan).

---

## 6. Responsive

| Breakpoint | Comportamiento |
|------------|----------------|
| Desktop ≥820 | Rails de proceso/automation horizontales (`min-width: 0`) |
| ≤1100 | Governance / catálogos a 1 columna |
| ≤820 | Rails de pipeline/assistant/copilot intake apilados |
| ≤768 | Sidebar full-width; copilot response rail apilado; formularios sin overflow |

---

## 7. Accesibilidad

Focus ring mineral; `prefers-reduced-motion` sin pulse; HTML compacto (sin indentación markdown que escape tags); strings escapados.

---

## 8. Reglas de implementación

1. Fuente de verdad: `assets/css/custom.css` (`--pd-*`).  
2. Clases explícitas desde Python; no nuevos `:has()` para fondos.  
3. Botones de sección acotados (topbar / launcher) sin filtración global.  
4. No cards repetidas para todo: tipografía + bordes semánticos.  
5. Helpers visuales huérfanos eliminados de `app/ui.py` (automation/governance legacy, Neural Canvas aliases no usados).

---

## 9. Límites pendientes

- `theme.py` / Plotly aún pueden espejar hex pre-mineral.  
- Landing marketing conserva aliases `--cyan*` y restos visuales.  
- QA visual exhaustivo en dispositivos reales.  
- Charts Plotly deep-retokenize.

# Building the Power BI canvas (MVP executive)

Requirements: **Power BI Desktop** (Windows). Steps assume data exported with `python scripts/export_powerbi_source.py`.

## 1. Data

1. Open Power BI Desktop → **Get Data** → **Text/CSV** (or **Folder** and select `bi/powerbi/source_csv/`).
2. Load each file with **Transform Data** and type if needed:
   - `AppointmentBase[appointment_date]` → **Date**
   - `BillingLine[billing_date]` → **Date**
   - `DimDate[date]` → **Date**
3. **Close & apply**.

**Table names:** rename in the fields pane to match `dax/executive_measures.dax` exactly: `AppointmentBase`, `BillingLine`, `DimBillingStatus`, `DimDate`, `DailyKpis`, `KpiBySpecialty`, `RevenueBridge`.

## 2. Relationships (Model view)

| From | To | Cardinality |
|------|-----|----------------|
| `DimDate[date]` | `AppointmentBase[appointment_date]` | 1:N |
| `AppointmentBase[appointment_id]` | `BillingLine[appointment_id]` | 1:N |
| `DimBillingStatus[billing_status_id]` | `BillingLine[billing_status_id]` | 1:N |
| `AppointmentBase[appointment_id]` | `RevenueBridge[appointment_id]` | 1:1 |

Do not relate `DailyKpis` or `KpiBySpecialty` to the calendar if used only as helper tables; or relate `DailyKpis[appointment_date]` to `DimDate[date]` only if types match (optional).

## 3. Measures

Create measures from [`dax/executive_measures.dax`](dax/executive_measures.dax) (paste one by one into `AppointmentBase` or a dedicated Measures table).

## 4. Interactions (important)

- **Billed revenue card:** metric uses **billing** (`billing_date`). Add a **slicer** on `BillingLine[billing_date]` (range) for this metric only.
- Under **Format → Edit interactions**, turn off influence from **schedule** slicers (specialty, provider, channel, appointment `DimDate`) on the **billed revenue** card so anchors are not mixed. Operational KPIs (volume, rates) should still respond to those slicers.

Acceptable alternative: leave default interactions knowing revenue reflects **lines tied to filtered appointments**, not pure “billing month” totals—then rename the card to **“Revenue (lines for filtered appointments)”**.

## 5. One “Executive” page

| Section | Visual | Fields |
|---------|--------|--------|
| **A Filters** | Slicers | `DimDate` hierarchy or `AppointmentBase[appointment_date]`; `specialty_name`; `provider_label`; `channel_code` |
| **B Cards** | Card (×5–6) | `[Citas Total]`, `[Citas Atendidas]`, `[No Show Rate]`, `[Tasa Cancelacion]`, `[Ingreso Facturado]`, `[Citas Atendidas Sin Facturacion]` |
| **C Trend** | Line chart | X: `AppointmentBase[appointment_date]` (by month); Value: `[Citas Atendidas]` |
| **D Breakdown** | Horizontal bar | Y: `specialty_name`; Value: `[Citas Atendidas]` |
| **E Alert** | Table or card | `[Citas Atendidas Sin Facturacion]` + helper text |

Page title: **Executive — Schedule (appointment date) / Billing (issue date on revenue card)**.

## 6. Save

Save as `Paradigm_executive.pbix` under `bi/powerbi/` (optional) or outside the repo if large.

## 7. Numeric validation

Run from repo root:

```bash
python scripts/validate_executive_kpis.py
```

Compare unfiltered totals with report cards (no active slicers).

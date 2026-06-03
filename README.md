# rdl-report-mcp

An MCP server for **authoring and editing SSRS / Power BI / Fabric paginated reports (RDL)**,
including **matrices** and multi-region layouts. Extends
[`bethmaloney/rdl-mcp`](https://github.com/bethmaloney/rdl-mcp) (the vendored base, MIT — see
`LICENSE.upstream`) with the ability to:

- **Create reports from scratch** against a **Fabric SQL endpoint**, a **SQL Server**, or a
  **Power BI semantic model (DAX)**.
- **Author from styled templates** — a small library of real, Report-Builder-authored
  archetypes (flat table, matrices, composites) that the engine clones and rebinds to your
  data. Far more robust than generating RDL element-by-element.
- **Edit existing reports** (the base tools): columns, datasets, parameters, validation.

The RDL engine is **transport-agnostic** (no MCP/stdio coupling) so it can later be reused
behind a REST/FastAPI service (e.g. a Microsoft Fabric custom workload).

> Status: 20 MCP tools, 6 verified template archetypes, 30 tests. See [`PROGRESS.md`](PROGRESS.md).

## Run

```bash
python rdl_report_mcp_server.py        # MCP server over stdio
python -m pytest tests/ -q             # run tests
```

MCP client config (stdio): run `rdl_report_mcp_server.py` with this repo on `PYTHONPATH`.

## Data sources

Pick a `source_type` and pass a `connection`:

| `source_type` | Target | `connection` keys |
|---|---|---|
| `fabric` | Fabric SQL endpoint (SQLAZURE, AAD interactive) | `data_source`, `initial_catalog` (or `connect_string`); `name` |
| `sql` | SQL Server (integrated security) | `data_source`, `initial_catalog` (or `connect_string`); `name` |
| `dax` | Power BI semantic model (PBIDATASET) | `connect_string` (recommended) **or** `initial_catalog`+`identity_provider`; plus `workspace_name`, `dataset_name`; `name` |

`fields` items are `{name, data_field?, type_name?}`. `data_field` defaults to `name`. For
**DAX**, set `data_field` to `Table[Column]` (dimensions) or `[Measure]` (measures).

> **Templates are source-agnostic**: a template's placeholder data source is *replaced* by
> your `source_type` at generation time, so every template works with `fabric`, `sql`, **or
> `dax`** — no per-source templates.

## Quick start — create a report from scratch

```python
from rdl_report_mcp import create_report

create_report(
    filepath="out.rdl", title="Monthly PnL", source_type="fabric",
    connection={"name": "fabric",
                "data_source": "<wh>.datawarehouse.fabric.microsoft.com",
                "initial_catalog": "<lakehouse>"},
    dataset_name="pnl",
    query="SELECT LOCATIONNAME, signed_amount FROM mv_pnl_actual WHERE batch_month IN (@Month)",
    fields=[{"name": "LOCATIONNAME"}, {"name": "signed_amount", "type_name": "System.Decimal"}],
    parameters=[{"name": "Month", "data_type": "String", "prompt": "Month"}],
)
```

The body is empty (no visual) — use a template for tables/matrices.

## Templates

`list_templates()` returns the library. Two entry points:

- **`create_report_from_template(...)`** — single-region templates (table or matrix).
- **`create_composite_report_from_template(...)`** — multi-region/multi-dataset templates.

| Template | Kind | What you bind |
|---|---|---|
| `styled_flat_table` | table | `fields` → one styled column each (`label`, `width`, `format` per field) |
| `simple_matrix` | matrix | `bindings`: `row_group`, `column_group`, `value` (+`aggregate`,`value_format`) |
| `matrix_grouped` | matrix | `bindings`: `row_groups=[outer,inner]`, `column_group`, `value` (+`row_group_labels`) |
| `matrix_and_table` | composite | `datasets=[MatrixData, TableData]`; `regions={matrix:{bindings}, table:{columns}}` |
| `matrix_and_matrix_paged` | composite | one Excel sheet per category; `datasets=[SummaryData, CategoryData]`; `regions={matrix:{bindings}, paged_matrix:{bindings:{row_groups:[category, inner], ...}}}` |
| `grouped_rectangle_matrices` | composite | grouped List/Rectangle, one sheet per category, 2 matrices/block; `datasets=[MatrixData]`; `regions={container:{group_field}, block1:{bindings}, block2:{bindings}}` |

Full copy-paste examples for every archetype: [`docs/TEMPLATES.md`](docs/TEMPLATES.md).

### Example — a matrix

```python
from rdl_report_mcp import create_report_from_template

create_report_from_template(
    filepath="matrix.rdl", template="simple_matrix", title="PnL", source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    dataset_name="pnl",
    query="SELECT LOCATIONNAME, batch_month, signed_amount FROM mv_pnl_actual",
    fields=[{"name": "LOCATIONNAME"}, {"name": "batch_month", "type_name": "System.DateTime"},
            {"name": "signed_amount", "type_name": "System.Decimal"}],
    bindings={"row_group": "LOCATIONNAME", "column_group": "batch_month",
              "value": "signed_amount", "aggregate": "Sum", "value_format": "N0"},
)
```

### Example — same matrix over a Power BI semantic model (DAX)

```python
create_report_from_template(
    filepath="matrix_dax.rdl", template="simple_matrix", title="PnL", source_type="dax",
    connection={"name": "pbi", "connect_string": "<ConnectString from a working PBI report>",
                "workspace_name": "Corporate", "dataset_name": "Finance"},
    dataset_name="pnl",
    query="EVALUATE SUMMARIZECOLUMNS(Loc[Name], Date[Month], \"Amt\", [Signed Amount])",
    fields=[{"name": "Name", "data_field": "Loc[Name]"},
            {"name": "Month", "data_field": "Date[Month]"},
            {"name": "Amt", "data_field": "[Signed Amount]", "type_name": "System.Decimal"}],
    bindings={"row_group": "Name", "column_group": "Month", "value": "Amt"},
)
```

## Tools (20)

**Authoring (new):** `create_report`, `add_dataset`, `list_templates`,
`create_report_from_template`, `create_composite_report_from_template`.

**Read (base):** `describe_rdl_report`, `get_rdl_datasets`, `get_rdl_parameters`,
`get_rdl_columns`, `validate_rdl`.

**Edit (base):** `update_column_header`, `update_column_width`, `update_column_format`,
`add_column`, `remove_column`, `update_stored_procedure`, `add_dataset_field`,
`remove_dataset_field`, `add_parameter`, `update_parameter`.

## How the template engine works

1. Each archetype lives in `rdl_report_mcp/templates/library/<name>/` as a **`template.rdl`**
   (a sanitized, Report-Builder-authored report — placeholder connection, no secrets) plus a
   **`manifest.json`** describing the bindable "slots" (groups, value cells, prototype column,
   regions).
2. On generation the engine clones the template, **replaces the data source** (from
   `source_type`/`connection`), **replaces the dataset(s)** (your query + fields), and rebinds
   the slots: table → stamps one styled column per field; matrix → sets row/column group
   expressions + value aggregate; `list` container → sets the group + Excel `PageName` + title.
3. Output is validated (`validate_rdl`) and namespaces round-trip cleanly.

### Adding a new archetype (the workflow)

1. Author a minimal example in **Power BI Report Builder**; verify it (incl. Excel export if it
   paginates). 2. Distill it: sanitize the connection string + IDs, drop it in
   `templates/library/<name>/template.rdl`, write `manifest.json`. 3. Reuse/extend the engine
   region kinds (`table`/`matrix`/`list`). 4. Add a test; verify in Report Builder.

## Notes

- RDL is fragile XML; templates are authored in Report Builder for guaranteed validity, then
  cloned + rebound rather than hand-generated.
- The engine fixes the base's default-namespace round-trip and rejects empty `<ReportItems>`.

## Attribution

Core read/edit modules are vendored from `bethmaloney/rdl-mcp` (MIT, `LICENSE.upstream`).
New modules (`report_builder`, `templates_lib`) and the template library are additions here.

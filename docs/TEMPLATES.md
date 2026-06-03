# Template cookbook

Copy-paste examples for every archetype in `rdl_report_mcp/templates/library/`. All examples
use `source_type="fabric"`; swap in `sql` or `dax` (see the [README](../README.md#data-sources)).
Run `list_templates()` to see what's installed.

Common notes:
- `fields` = the dataset fields: `{name, data_field?, type_name?}` (+ `label`/`width`/`format`
  for table columns). `data_field` defaults to `name`; for DAX use `Table[Column]` / `[Measure]`.
- `aggregate` ∈ `Sum|Avg|Count|Min|Max|First` (default `Sum`). `value_format` is an SSRS format
  string (e.g. `N0`, `P2`, `MM/dd/yyyy`).

---

## styled_flat_table  — `create_report_from_template`

One styled column per field (blue header band, bordered cells).

```python
from rdl_report_mcp import create_report_from_template

create_report_from_template(
    filepath="table.rdl", template="styled_flat_table", title="Census",
    source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    dataset_name="census",
    query="SELECT facility, resident, admit_date, days FROM census",
    fields=[
        {"name": "facility", "label": "Facility", "width": "2in"},
        {"name": "resident", "label": "Resident"},
        {"name": "admit_date", "label": "Admit Date", "format": "MM/dd/yyyy"},
        {"name": "days", "label": "Days", "type_name": "System.Int32", "format": "N0"},
    ],
)
```

## simple_matrix  — `create_report_from_template`

1 row group × 1 column group × 1 value.

```python
create_report_from_template(
    filepath="m.rdl", template="simple_matrix", title="PnL", source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    dataset_name="pnl",
    query="SELECT LOCATIONNAME, batch_month, signed_amount FROM mv_pnl_actual",
    fields=[{"name": "LOCATIONNAME"}, {"name": "batch_month", "type_name": "System.DateTime"},
            {"name": "signed_amount", "type_name": "System.Decimal"}],
    bindings={"row_group": "LOCATIONNAME", "column_group": "batch_month",
              "value": "signed_amount", "aggregate": "Sum", "value_format": "N0"},
)
```

## matrix_grouped  — `create_report_from_template`

Nested row groups (outer → inner) × column group × value. `row_group_labels` names the two
corner cells.

```python
create_report_from_template(
    filepath="mg.rdl", template="matrix_grouped", title="PnL by Region/Facility",
    source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    dataset_name="pnl",
    query=("SELECT LEFT(LOCATIONNAME,3) AS region, LOCATIONNAME, batch_month, signed_amount "
           "FROM mv_pnl_actual"),
    fields=[{"name": "region"}, {"name": "LOCATIONNAME"},
            {"name": "batch_month", "type_name": "System.DateTime"},
            {"name": "signed_amount", "type_name": "System.Decimal"}],
    bindings={"row_groups": ["region", "LOCATIONNAME"], "column_group": "batch_month",
              "value": "signed_amount", "aggregate": "Sum", "value_format": "N0",
              "row_group_labels": ["Region", "Facility"]},
)
```

## matrix_and_table  — `create_composite_report_from_template`

Summary matrix on top + detail table below, **two datasets**.

```python
from rdl_report_mcp import create_composite_report_from_template

create_composite_report_from_template(
    filepath="mt.rdl", template="matrix_and_table", title="Summary + Detail",
    source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    datasets=[
        {"name": "MatrixData",
         "query": ("SELECT LOCATIONNAME, batch_month, SUM(signed_amount) AS Val "
                   "FROM mv_pnl_actual GROUP BY LOCATIONNAME, batch_month"),
         "fields": [{"name": "LOCATIONNAME"}, {"name": "batch_month", "type_name": "System.DateTime"},
                    {"name": "Val", "type_name": "System.Decimal"}]},
        {"name": "TableData",
         "query": "SELECT TOP 100 LOCATIONNAME, accountno_level, signed_amount FROM mv_pnl_actual",
         "fields": [{"name": "LOCATIONNAME"}, {"name": "accountno_level", "type_name": "System.Int32"},
                    {"name": "signed_amount", "type_name": "System.Decimal"}]},
    ],
    regions={
        "matrix": {"bindings": {"row_group": "LOCATIONNAME", "column_group": "batch_month",
                                "value": "Val", "aggregate": "Sum", "value_format": "N0"}},
        "table": {"columns": [{"name": "LOCATIONNAME", "label": "Facility", "width": "50mm"},
                              {"name": "accountno_level", "label": "Level"},
                              {"name": "signed_amount", "label": "Amount", "format": "N0"}]},
    },
)
```

## matrix_and_matrix_paged  — `create_composite_report_from_template`

Summary matrix, then a second matrix that **breaks into one Excel worksheet per category**
(named by the category field). `paged_matrix.bindings.row_groups = [category, inner_row]`.

```python
create_composite_report_from_template(
    filepath="mmp.rdl", template="matrix_and_matrix_paged", title="PnL + per-region sheets",
    source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    datasets=[
        {"name": "SummaryData",
         "query": ("SELECT LOCATIONNAME, batch_month, SUM(signed_amount) AS Val "
                   "FROM mv_pnl_actual GROUP BY LOCATIONNAME, batch_month"),
         "fields": [{"name": "LOCATIONNAME"}, {"name": "batch_month", "type_name": "System.DateTime"},
                    {"name": "Val", "type_name": "System.Decimal"}]},
        {"name": "CategoryData",
         "query": ("SELECT LEFT(LOCATIONNAME,3) AS region, LOCATIONNAME, batch_month, "
                   "signed_amount AS Val FROM mv_pnl_actual"),
         "fields": [{"name": "region"}, {"name": "LOCATIONNAME"},
                    {"name": "batch_month", "type_name": "System.DateTime"},
                    {"name": "Val", "type_name": "System.Decimal"}]},
    ],
    regions={
        "matrix": {"bindings": {"row_group": "LOCATIONNAME", "column_group": "batch_month",
                                "value": "Val", "aggregate": "Sum", "value_format": "N0"}},
        "paged_matrix": {"bindings": {"row_groups": ["region", "LOCATIONNAME"],
                                      "column_group": "batch_month", "value": "Val",
                                      "aggregate": "Sum", "value_format": "N0"}},
    },
)
```

The `region` field drives the page break **and** the worksheet name (PageName).

## grouped_rectangle_matrices  — `create_composite_report_from_template`

A List grouped by category whose Rectangle holds a block title + **two independently-bindable
matrices**; one block (and Excel sheet) per category. **One shared dataset.**

```python
create_composite_report_from_template(
    filepath="gr.rdl", template="grouped_rectangle_matrices", title="Blocks per facility",
    source_type="fabric",
    connection={"name": "fabric", "data_source": "<wh>...", "initial_catalog": "<lh>"},
    datasets=[{"name": "MatrixData",
               "query": ("SELECT LOCATIONNAME AS Category, batch_month AS ColCat, "
                         "Level1 AS RowA, Level2 AS RowB, SUM(signed_amount) AS Rev, "
                         "SUM(census_denom_main) AS Days FROM mv_pnl_actual "
                         "GROUP BY LOCATIONNAME, batch_month, Level1, Level2"),
               "fields": [{"name": "Category"}, {"name": "ColCat", "type_name": "System.DateTime"},
                          {"name": "RowA"}, {"name": "RowB"},
                          {"name": "Rev", "type_name": "System.Decimal"},
                          {"name": "Days", "type_name": "System.Decimal"}]}],
    regions={
        "container": {"group_field": "Category"},   # drives grouping, page break, sheet name, title
        "block1": {"bindings": {"row_group": "RowA", "column_group": "ColCat",
                                "value": "Rev", "value_format": "N0"}},
        "block2": {"bindings": {"row_group": "RowB", "column_group": "ColCat",
                                "value": "Days", "value_format": "N0"}},
    },
)
```

`container` also accepts an optional `title` (expression/label); it defaults to the category value.

---

## add_dataset — attach a lookup/parameter dataset

```python
from rdl_report_mcp import add_dataset

add_dataset("table.rdl", dataset_name="regions",
            query="SELECT DISTINCT LEFT(LOCATIONNAME,3) AS region FROM mv_pnl_actual",
            fields=[{"name": "region"}])   # binds to the report's existing data source
```

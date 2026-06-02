# PROGRESS — rdl_report_mcp

Durable task tracker for the multi-session build. **Read this first each session.** Update
after every completed task (check the box, add a one-line note + commit hash). Full plan:
`C:\Users\vhuyd\.claude\plans\ethereal-doodling-nest.md`.

Goal: extend `bethmaloney/rdl-mcp` (vendored at `rdl_report_mcp/`) to scaffold new paginated
reports (Fabric SQLAZURE / plain SQL / Power BI DAX) and author **matrices** (add matrix,
add value column, add row/column groups). Keep the stdlib JSON-RPC server; keep the RDL
engine transport-agnostic (future Fabric workload reuse).

Reference RDLs in `fabric_report_tool/`: matrix skeleton = `power semantic model as source/Weekly Enrollment Trend.rdl`;
DAX flat table = `Raw Enrollment Revenue.rdl`; plain-SQL = `sql script as source/Executive Dashboard PBI.rdl`;
deep matrix fragments = `Hill Valley report.rdl` (root). Excel ground-truth: matching `.xlsx`.

## Phase 0 — Scaffold
- [x] T0.1 PROGRESS.md + `rdl_report_mcp/` + `tests/` dirs
- [x] T0.2 `pyproject.toml` + entry `rdl_report_mcp_server.py`; `initialize`+`tools/list` (15 tools) respond ✓

## Phase 1 — Vendor base & confirm seam
- [x] T1.1 Vendored base `rdl_mcp/*` → `rdl_report_mcp/` (relative imports, package renamed via dir)
- [x] T1.2 Base read tools on copy of `Hill Valley report.rdl`: describe (6 ds/3 params), datasets, validate=valid ✓ (get_rdl_columns=0 → matrix gap, as expected)
- [x] T1.3 Seam verified: no engine module imports `server`; `server.py` imports engine modules

## Phase 2 — create_report (fabric SQLAZURE + plain SQL)
- [ ] T2.1 `templates/report_skeleton_sql.rdl`
- [ ] T2.2 `report_builder.create_report(source_type in {fabric,sql})`
- [ ] T2.3 Register tool in `server.py`
- [ ] T2.4 Verify: validate_rdl passes; opens in Report Builder w/ data

## Phase 3 — create_report (DAX) + add_dataset
- [ ] T3.1 `templates/report_skeleton_dax.rdl`
- [ ] T3.2 DAX branch (CommandText-only; DataField Table[Col]/[Measure])
- [ ] T3.3 `add_dataset(...)`
- [ ] T3.4 Verify in Report Builder vs semantic model

## Phase 4 — add_matrix (1×1×1)
- [ ] T4.1 `templates/matrix_skeleton.xml` from Weekly Enrollment Trend
- [ ] T4.2 `fragments.py` (load/clone_and_bind/unique_name/locators)
- [ ] T4.3 `matrix.add_matrix(...)`
- [ ] T4.4 Register tool + schema
- [ ] T4.5 Verify: renders a pivot

## Phase 5 — add_matrix_value ("add column")
- [ ] T5.1 `fragments/value_cell.xml`
- [ ] T5.2 `matrix.add_matrix_value(...)`
- [ ] T5.3 Register + verify column sums in Report Builder

## Phase 6 — add_matrix_row_group / add_matrix_column_group
- [ ] T6.1 `fragments/row_group.xml`, `fragments/column_group.xml`
- [ ] T6.2 `add_matrix_row_group(...)`
- [ ] T6.3 `add_matrix_column_group(...)`
- [ ] T6.4 Register + verify nested groups vs xlsx ground-truth

## Phase 7 — Inverse ops, validation, tests, docs
- [ ] T7.1 `remove_matrix_group` / `remove_matrix_value`
- [ ] T7.2 matrix-aware `validate_rdl`
- [ ] T7.3 round-trip tests for every tool
- [ ] T7.4 README/usage docs; finalize

## Phase 8 (future) — Fabric workload / REST
- [ ] Not scheduled. Gate: MCP engine stable + tested.

## Session log
- 2026-06-02: Phase 0/1 started — vendored base, scaffolding.

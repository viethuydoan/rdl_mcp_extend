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
- [x] T2.1 `templates/report_skeleton_sql.rdl` (sanitized, placeholder conn)
- [x] T2.2 `report_builder.create_report(source_type in {fabric,sql})` + QueryParameters + ReportParameters
- [x] T2.3 Registered in `server.py` (16 tools); exported in `__init__`
- [x] T2.4 Opens cleanly in Report Builder (after empty-ReportItems fix); conn string +
      dataset SQL present. validate_rdl=valid, MCP stdio smoke OK, 7 pytest pass. ✓ SIGNED OFF

## Phase TM — Matrix templates (Strategy A: pre-structured, rebind fields)
- [x] TM.1 `simple_matrix` distilled from user-authored `minimal_matrix.rdl` (sanitized:
      placeholder conn, zeroed IDs; #305496 col-header band) + manifest (structure=matrix, slots)
- [x] TM.2 `templates_lib` dispatches on manifest `structure`; added `_rebind_matrix`
      (sets row/col GroupExpression + SortExpression + header textboxes + value aggregate/format)
- [x] TM.3 `create_report_from_template` gains `bindings` arg (row_group/column_group/value/
      aggregate/value_format); server schema+delegate updated. 16 tests pass; MCP matrix smoke OK.
- [x] TM.4 Verified in Report Builder — renders a pivot (rows x columns, #305496 header,
      aggregated cells). ✓ SIGNED OFF. Matrix-template pipeline proven.
- Next matrix archetypes (later): matrix_grouped (nested row groups), matrix_and_table.

## Phase TMT — matrix_and_table (composite: 2 datasets, 2 regions)
- [x] TMT.1 Distilled `matrix_and_table` from user-authored `minimal_matrix_and_table.rdl`
      (sanitized; MatrixTablix on top + TableTablix below, MatrixData/TableData, #305496 bands)
- [x] TMT.2 Refactored engine to region-based (`_rebind_matrix_region`, `_rebind_table_region`,
      `_find_tablix`, `_set_region_dataset`); single-region path unchanged.
- [x] TMT.3 New `create_composite_report_from_template(datasets[], regions{})` tool (19 total);
      manifest structure=composite with regions{matrix,table}. 22 tests pass; MCP smoke OK.
- [x] TMT.4 Verified in Report Builder — matrix on top + detail table below, both bound. ✓ SIGNED OFF.

## Phase TMM — matrix_and_matrix_paged (2nd matrix breaks to 1 Excel sheet per Category/region)
RDL mechanism: page-break group = Group with <PageBreak><BreakLocation>Between</BreakLocation></PageBreak>
+ dynamic <PageName>=Fields!Category.Value</PageName> (Excel renderer names each worksheet from PageName).
- [x] TMM.1 User authored matrix_and_matrix_paged.rdl + verified Excel export (1 sheet per category)
- [x] TMM.2 Distilled (sanitized-copy of the working file) into matrix_and_matrix_paged template +
      composite manifest. Matrix2: Category = pagination-only group (PageBreak Between + PageName,
      no header) + RowCat1 visible inner. `_rebind_group` now rebinds PageName + tolerates header-less
      groups. PageBreak/PageName baked in template; engine only swaps the field. 5 archetypes total.
- [x] TMM.3 Verified in Report Builder + Excel export → one sheet per category. ✓ SIGNED OFF.

## Phase TMR — grouped-rectangle of multiple matrices (N matrices per group instance)
Pattern: a List (Tablix with one detail cell) grouped by Category, detail cell holds a Rectangle
containing N matrices (+ optional title). Rectangle repeats per group. Nested data regions in a
grouped scope SHARE the list's dataset (scoped/filtered to the current group automatically).
- [x] TMR.1 User authored + trimmed matrix_rectangle_grouped.rdl (List by Category → Rectangle →
      2 single-value matrices) + verified Excel export (1 sheet per category)
- [x] TMR.2 Distilled `grouped_rectangle_matrices` (sanitized). New composite region kind `list`:
      rebinds the container group (expr+sort), the Rectangle PageName (note: in a List the PageName
      is on the Rectangle, not the Group), and the block title. Two independently-bindable
      single-value matrix regions (block1/block2), one shared dataset. 6 archetypes.
- [~] TMR.3 25 tests pass (container/title/blocks + PageName rebind + group_field guard), validate OK.
      **PENDING USER:** open in Report Builder + Export to Excel → one sheet per category, each with
      title + 2 matrices.

## Phase TMG — matrix_grouped (nested row groups)
- [x] TMG.1 Distilled `matrix_grouped` from user-authored `minimal_matrix_grouped.rdl`
      (sanitized; outer/inner row groups RowGroupOuter/RowGroupInner, #305496 corner+col band)
- [x] TMG.2 Generalized `_rebind_matrix` for N row groups; `_rebind_group` now scopes the
      SortExpression to the group's own TablixMember (fixes nested-group sort targeting).
      bindings.row_groups=[outer,inner] + optional row_group_labels for corner cells.
- [x] TMG.3 19 tests pass (incl. independent-sort + corner-label + wrong-count); validate OK.
- [x] TMG.4 Verified in Report Builder — nested rows render under the outer group. ✓ SIGNED OFF.
      Per user, removed the DimGray LeftBorder accent from the template (value cell + col header).

## Phase T — Template mode (user priority: build before Phase 3)
Start from full styled archetypes (cloned + rebound) rather than bare skeletons. First
archetype: **styled flat table** (distilled from `Raw Enrollment Revenue.rdl`). Templates
live in `rdl_report_mcp/templates/library/<name>/` = `template.rdl` + `manifest.json` (slots).
Rebind via ElementTree (swap datasource/dataset, stamp one styled column per field from a
prototype cell). Sanitized: placeholder connection strings only.
- [x] TT.1 Library layout `templates/library/<name>/{template.rdl,manifest.json}` + manifest schema
- [x] TT.2 Distilled `styled_flat_table` (sanitized; #305496 header band, prototype cells)
- [x] TT.3 `templates_lib.py` engine: load template, clone prototype cells, stamp N columns
- [x] TT.4 `create_report_from_template(...)` (reuses Phase 2 _add_datasource/_add_dataset)
- [x] TT.5 `list_templates()` + both tools registered (18 total); exported
- [x] TT.6 Verified in Report Builder — styled table renders (blue header, bordered cells),
      loads clean, previews rows. ✓ SIGNED OFF. Template-mode approach validated.

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
- 2026-06-02: Phase 0/1 done & pushed (scaffold, vendored base, seam verified).
- 2026-06-02: Fixed critical namespace bug in `xml_utils.register_namespaces` — base
  `write_xml` was emitting `<ns0:Report>` and dropping default `xmlns`; now registers the
  default ns with empty prefix so RDL round-trips cleanly. Prereq for all generation.
- 2026-06-02: Phase 2 built — `create_report` (fabric/sql) + skeleton + server wiring + 5
  tests. validate_rdl "No Tablix" downgraded to warning.
- 2026-06-02: Report Builder REJECTED v1 skeleton: empty `<ReportItems/>` = "incomplete
  content". Fix: omit ReportItems for empty body (it's minOccurs=0); added validate_rdl rule
  to flag empty ReportItems; +2 regression tests (7 total pass). Awaiting user retest (T2.4).
- 2026-06-02: Phase T (template mode) built — styled_flat_table archetype + manifest,
  templates_lib engine (clone prototype cells, stamp 1 styled column/field), list_templates +
  create_report_from_template tools (18 total), 12 tests pass. Awaiting user RB check (TT.6).
- 2026-06-02: TT.6 + matrix mode done. simple_matrix template + _rebind_matrix + bindings
  arg. Both archetypes (styled_flat_table, simple_matrix) verified in Report Builder. 16 tests.
- Next (user to choose): matrix_grouped / matrix_and_table archetypes, or Phase 3 (DAX,
  which gives template mode DAX for free), or Strategy B dynamic group/value editing.

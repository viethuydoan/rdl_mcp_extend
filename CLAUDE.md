# CLAUDE.md — rdl_report_mcp

Guidance for Claude Code when working in this repo.

## What this is
An MCP server that **authors and edits SSRS / Fabric / Power BI paginated reports (RDL)** —
create reports from scratch or from a library of styled, Report-Builder-authored **templates**
(flat table, matrices, composites), against **Fabric SQL / SQL Server / Power BI DAX** sources.
Vendored + extended from `bethmaloney/rdl-mcp` (MIT, `LICENSE.upstream`).

## Resume convention (READ FIRST each session)
1. Read **`PROGRESS.md`** — the **▶ NEXT SESSION** block at the top has the current plan/state.
2. Skim **`README.md`** (API, 20 tools, 6 archetypes, source types) and **`docs/TEMPLATES.md`**
   (copy-paste examples). `tests/` shows engine-helper usage.
3. Update `PROGRESS.md` after each task; **commit per task** (small, verifiable).

## Status (2026-06-02)
Phases 0–3 + the 6-template library are **done, Report-Builder-verified, documented, pushed**.
20 MCP tools, 30 tests. **Next up = Phase SB (Strategy B): edit EXISTING matrices** (add/remove
row group, column group, value). Plan is in `PROGRESS.md`.

## Architecture rules
- **Transport-agnostic engine:** report logic lives in `report_builder.py` / `templates_lib.py`
  and never imports `server`; `server.py` is a thin stdio/JSON-RPC layer. Keep this seam (it
  enables a future Fabric-workload / FastAPI wrapper).
- **Templates are source-agnostic:** the placeholder datasource is rebuilt from `source_type`,
  so every template works for fabric/sql/dax. Don't add per-source template duplicates.
- **RDL is fragile:** prefer the proven workflow — the user authors a minimal (or before/after)
  example in Report Builder; sanitize-copy it (scrub connection string + GUIDs) into
  `templates/library/<name>/` and learn the exact XML by diffing — rather than hand-generating
  matrix XML. Verify generated RDL opens in Report Builder (the real gate; `validate_rdl` is
  necessary but not sufficient).
- Every `Name=` (Tablix/Textbox/Group) must be globally unique. Keep namespaces round-tripping
  (the default-namespace fix lives in `xml_utils.register_namespaces`).

## Git
Remote `origin` = `https://github.com/viethuydoan/rdl_mcp_extend.git` (personal **viethuydoan**
identity). Per global rules, confirm the account before any new remote-touching action.

## Environment
Python: `/c/Users/vhuyd/anaconda3/python.exe` (Anaconda base). Run server:
`python rdl_report_mcp_server.py`. Tests: `python -m pytest tests/ -q`. Reference RDLs the
templates were distilled from live in the sibling repo `Hill Valley/fabric_report_tool/` (not
in this repo — they contain real connection strings/data; never commit them here).

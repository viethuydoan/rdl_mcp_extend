# rdl-report-mcp

An MCP server for **authoring and editing SSRS / Power BI / Fabric paginated reports (RDL)**,
including **matrices**. Extends [`bethmaloney/rdl-mcp`](https://github.com/bethmaloney/rdl-mcp)
(the vendored base, MIT — see `LICENSE.upstream`) with the ability to:

- **Create a new report from scratch** against a Fabric SQL endpoint, a plain SQL Server, or
  a Power BI semantic model (DAX).
- **Author matrices**: add a matrix, add value/measure columns, add row groups and column
  groups — which the flat-table-only base cannot do.

The RDL engine is kept **transport-agnostic** (no MCP/stdio coupling) so it can later be
reused behind a REST/FastAPI service (e.g. a Microsoft Fabric custom workload).

## Status

Early development. See [`PROGRESS.md`](PROGRESS.md) for the phased task list and current state.

## Run

```bash
python rdl_report_mcp_server.py     # speaks MCP JSON-RPC over stdio
```

## Layout

```
rdl_report_mcp/        # the package (vendored base + new modules)
  reader/columns/datasets/parameters/validation/xml_utils/server  # base
  report_builder.py    # create_report (SQL / DAX)        [in progress]
  matrix.py            # matrix authoring                  [planned]
  fragments.py         # template fragment engine          [planned]
  templates/           # sanitized RDL skeletons + fragments (placeholder conn strings)
rdl_report_mcp_server.py   # stdio entry point
tests/
```

## Attribution

Core read/edit modules are vendored from `bethmaloney/rdl-mcp` (MIT). New modules
(`report_builder`, `matrix`, `fragments`) and templates are additions in this repo.

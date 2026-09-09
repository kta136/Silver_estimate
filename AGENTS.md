## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Numeric Purity/Tunch

- Numeric `purity` is a commercial calculation multiplier and may exceed 100%.
  Never impose a 100% cap in UI, validation, imports, estimate saves, inventory,
  or printing. Reject negative and non-finite numeric values.
- Fine weight is net weight × purity / 100, rounded with the shared numeric
  policy; 10.00 g at 125.50% yields 12.55 g. Fine weight may exceed net weight.
- Optional `tunch` is separate free text with no percentage cap; it does not
  drive calculations. Preserve it in catalog transfers and estimate snapshots.
- Keep regression coverage for above-100 values across catalog writes/transfers,
  calculation, save/reload, inventory, and print. See
  `DOCS/workflow-business-logic.md` for the business rule.

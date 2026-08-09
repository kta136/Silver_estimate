---
type: "query"
date: "2026-08-09T11:54:59.548187+00:00"
question: "when enterin\\g values in estimate screen thw whole table is outlined with blue color on every entry. Why?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["EstimateTableView", "NumericDelegate", "ESTIMATE_ENTRY_STYLESHEET"]
---

# Q: when enterin\g values in estimate screen thw whole table is outlined with blue color on every entry. Why?

## Answer

Expanded from original query via graph vocab: [estimate, entry, table, view, input, focus, edit, editor, delegate, selection, style, stylesheet]. The outer blue frame is caused by QTableView#EstimateTableView:focus in estimate_entry_theme.py, which sets a 2px solid __FOCUS_RING__ border. __FOCUS_RING__ resolves to #2563eb in theme_tokens.py. The entry workflow repeatedly sets the current index and begins editing, so focus is re-established and the rule reapplies. A separate descendant QLineEdit rule also gives the active cell editor the same blue focus-ring color. This is intentional focus styling, not a data validation failure.

## Outcome

- Signal: useful

## Source Nodes

- EstimateTableView
- NumericDelegate
- ESTIMATE_ENTRY_STYLESHEET
---
type: "codebase"
date: "2026-07-16T06:39:20.496399+00:00"
question: "Program does start very fast but since user cannot type anything until all things all load, it looks like program is hung up"
contributor: "graphify"
outcome: "useful"
source_nodes: ["MainWindow", "EstimateEntryWidget", "ApplicationBuilder", "NavigationController", "LiveRateController"]
---

# Q: Program does start very fast but since user cannot type anything until all things all load, it looks like program is hung up

## Answer

The startup shell painted quickly, but the next UI-thread callback built the estimate workspace, delayed first-cell editing by 100 ms, and initialized menus/live rates before input got priority. The fix adds an explicit indeterminate loading state, starts the first code-cell editor on the first visible event-loop turn without stealing a user's early selection, and defers nonessential runtime services until 100 ms after the input surface is ready.

## Outcome

- Signal: useful

## Source Nodes

- MainWindow
- EstimateEntryWidget
- ApplicationBuilder
- NavigationController
- LiveRateController
# Visual references and generated output

The current print regression baselines are the semantic golden fixtures in
[tests/golden](../tests/golden), plus the real painter/PDF tests in
[tests/ui/test_print_manager.py](../tests/ui/test_print_manager.py). Golden files
are intentional test inputs, not generated clutter. They cover current print
content; PDF/painter tests cover rendering and pagination behavior.

## Curated historical references

The files below are retained from earlier visual reviews. They are historical
examples, not pixel-perfect expectations for the current source. Changes to
precision, snapshot metadata or layout can make current output differ.

| Example | PDF | PNG |
|---|---|---|
| Classic estimate | [PDF](../output/pdf/estimate-classic-short-headers-a4.pdf) | [PNG](../output/pdf/estimate-classic-short-headers-a4.png) |
| Modern estimate | [PDF](../output/pdf/modern-estimate-a4-semantic.pdf) | [PNG](../output/pdf/modern-estimate-a4-semantic.png) |
| Modern multipage estimate | [PDF](../output/pdf/modern-estimate-multipage.pdf) | [Page 1](../output/pdf/modern-estimate-multipage-page-1.png), [Page 2](../output/pdf/modern-estimate-multipage-page-2.png), [Page 3](../output/pdf/modern-estimate-multipage-page-3.png) |
| Silver-bar inventory | [PDF](../output/pdf/silver-bar-inventory-modern-a4.pdf) | [PNG](../output/pdf/silver-bar-inventory-modern-a4.png) |
| Silver-bar list | [PDF](../output/pdf/silver-bar-list-modern-a4.pdf) | [PNG](../output/pdf/silver-bar-list-modern-a4.png) |

The [July print-preview audit](../output/gui-audit/print-preview/AUDIT.md) and
its eleven screenshots are preserved together so its before/after evidence
and relative image references remain intact. The curated set contains 24 files:
12 report samples and 12 audit files.

## Generate current evidence

From the repository root, with the project virtual environment active:

```powershell
python -m pytest tests/ui/test_print_manager.py --basetemp=artifacts/print-reference-run
python -m pytest tests/smoke/test_full_startup_smoke.py --run-smoke --smoke-screenshots --smoke-artifact-dir=artifacts/current-ui-reference
```

The first command regenerates synthetic PDFs in pytest's temporary test
subdirectories. `--basetemp` replaces that dedicated run directory. The second
captures the current login, entry, history, settings and preview workflow with
synthetic data and isolated credentials. These commands reproduce current
behavior; they do not promise byte-identical historical screenshots.

New generated output belongs under ignored `artifacts/`. Root `tmp/` and
`output/` are ignored for future runs; the curated files already tracked under
`output/` remain versioned. Do not add repeated run directories or local pytest
symlinks to the repository.

The September cleanup removed 107 unreferenced temporary/superseded files after
reference checks. A local checksum manifest and verified archive are retained
under `artifacts/project-review/cleanup-visual-manifest.json` and
`artifacts/project-review/cleanup-removed-visuals.zip`. These are local audit
artifacts, not required runtime/build/test inputs.

# Print Preview GUI Audit

Date: 26 July 2026

## Scope

Combined UX and screenshot-based accessibility review of the Modern estimate
preview at 1280 × 820 and 800 × 720, plus the More menu.

User goal: verify the report, adjust its layout, navigate pages, export, or
print without hunting for controls.

## Before

1. `01-before-wide.png` — Functional, but Fit controls were icon-only despite
   available space and related report/view controls had no clear hierarchy.
2. `02-before-compact.png` — The More menu and later toolbar controls overflowed,
   leaving an ambiguous narrow extension button.
3. `03-before-more-menu.png` — Actions were understandable, but page navigation
   was hidden inside the menu even on wide screens.

## Improvements

- Split the preview chrome into primary and report-settings rows.
- Kept Print, Export PDF, More, Fit Width, Fit Page, zoom, and page number in
  the primary row.
- Kept orientation, estimate format, Tunch visibility, and Print Font in a
  stable settings row.
- Made Fit Width and Fit Page labels visible.
- Exposed the current page and total page count without opening a menu.
- Lightened the preview canvas while retaining clear page separation.
- Removed the redundant page-number widget from the More menu.

## After

1. `04-after-wide.png` — Healthy. Primary actions, view controls, page state,
   and report settings have distinct, readable groups.
2. `07-after-compact-final.png` — Healthy. All core controls and the page number
   remain visible at 800 px without toolbar overflow.
3. `06-after-more-menu.png` — Healthy. The menu is shorter and focused on
   printer setup, page setup, view mode, keyboard navigation, and close.

## Accessibility Notes

- Visible text now accompanies the less obvious Fit controls.
- Existing keyboard shortcuts for print, export, zoom, fit, and page navigation
  remain active.
- The page spin box has an accessible name and a direct-jump tooltip.
- Controls retain the application's focus, hover, checked, and disabled states.

Screenshot evidence cannot confirm screen-reader announcements, Windows
high-contrast behavior, or physical-printer dialogs. Those require runtime
assistive-technology and device testing.

## Intermediate icon refinement

- Kept visible text only for the primary Print and Export PDF actions.
- Converted fit, zoom, Print Font, and More to icon-only controls with retained
  tooltips, shortcuts, and accessible names.
- Reordered the primary row as output, view, page state, then overflow; report
  settings and font remain together in the second row.
- Added distinct `A` and ellipsis icons for Print Font and More.

This intermediate two-row state was superseded by the single-row consolidation
below. Evidence: `08-icon-order-wide.png` and `09-icon-order-compact.png`.

## Single-row consolidation

- Combined output, report settings, view controls, page state, and overflow into
  one physical toolbar.
- Removed the redundant `Report settings` label and second toolbar.
- Converted Print and Export PDF to icon-only controls so the complete toolbar
  remains visible at 800 px.
- Preserved the readable orientation, format, Tunch, and page-number values.

Evidence: `10-single-row-wide.png` and `11-single-row-compact.png`.

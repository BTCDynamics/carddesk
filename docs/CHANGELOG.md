# CardDesk Changelog

_Last updated: 2026-06-10_

This is a human-readable project history. Keep adding entries when major features, refactors, or recovery fixes are made.

## 2026-06-10

### Documentation Survival Pack
- Added `docs/` project documentation set.
- Added project map, database map, route map, deployment guide, recovery guide, features guide, changelog, and survival checklist.

### Route Audit Utility
- Added local route audit workflow.
- Purpose: catch missing Flask endpoints referenced by templates before deployment.
- Helped identify missing endpoints such as bulk card delete/image inbox routes.

### DB Schema Audit Utility
- Added local database schema audit workflow.
- Purpose: catch model/database mismatch issues before Render deploys.

### Route Mismatch Recovery
- Fixed missing route endpoints that caused Render page failures.
- Confirmed `/cards` route failure was caused by template endpoints missing from route modules, not by GitHub or Render repo mismatch.

### Intake Batch Updates
- Batch workflow includes create/open/close/reopen.
- Active batch context displays during AI Review and Mobile Capture.
- Batch detail can show imported cards and staged cards.
- Batch default storage location can be updated.

### Mobile Capture Updates
- Active batch awareness added.
- Auto-save behavior adjusted so camera workflow stays usable.
- Capture upload and image inbox workflows are available.

### Storage Location Dropdown Updates
- Storage entry locations were converted toward managed dropdown behavior across add/edit/rapid entry/AI review/batch/mobile workflows.
- Storage Explorer manages the location list.

### Show Prep / Event Updates
- Show Prep supports selected storage locations/loadouts.
- Show Prep print sheet added.
- Show calculations and drill-downs are intended to respect selected show/loadout locations.
- Events include show detail, show history, close report, and expenses/table fee tracking.

## 2026-06-09

### Event / Show Prep Refactor
- Dealer Hub event area moved toward create/manage show workflow.
- Show wording made more consistent.
- Show Prep loadout and checklist behavior improved.
- Stale inventory filtering fixed to avoid counting unrelated storage locations.

## Earlier Milestones

### Modular Refactor
- App moved from large monolithic `app.py` toward modular route files in `modules/`.
- Shared logic moved into `helpers/`.
- Route registration centralized in `app.py`.

### Dashboard / Dealer Hub Improvements
- Business Dashboard and Dealer Hub became separate operational views.
- Dealer Hub became primary workflow command center.
- Dashboard focuses more on metrics and analytics.

### Inventory Workflow
- Card list filters, active inventory views, sold/holding/all record scopes, storage filters, and pull sheet links were improved.
- Card detail supports inventory, batch, image, storage, quick sell, edit, clone, duplicate, and delete workflows.

### Sales / Fulfillment
- Quick Sell and Bulk Sell workflows added/refined.
- Deal Cart supports selected card lot sale.
- Fulfillment queue tracks pull, ship, and delivered status.

### AI Import / PSA Scanning
- AI Review queue added for staged imports.
- PSA lookup and scanner tools added for graded card workflows.

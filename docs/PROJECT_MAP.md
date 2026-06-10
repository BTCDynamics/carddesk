# CardDesk Project Map

_Last updated: 2026-06-10_

## Purpose

CardDesk is a Flask application for sports card dealer inventory management. It supports inventory tracking, dealer/show preparation, sales workflow, fulfillment, AI-assisted intake, PSA scanning, storage management, and operational dashboards.

## Core Structure

```text
app.py                  Main Flask app, configuration, global helpers, route registration
models.py               SQLAlchemy models
config.py               Application configuration
extensions.py           Shared Flask extension objects
modules/                Route files grouped by feature
helpers/                Shared business logic and utility helpers
templates/              Jinja2 HTML templates
static/css/carddesk.css Main styling
tools/                  Local developer audit utilities
docs/                   Project recovery and knowledge base
```

## Route Modules

The current app registers these route modules from `app.py`:

```text
- register_storage_routes(app)
- register_dashboard_routes(app)
- register_batch_routes(app)
- register_sales_routes(app)
- register_psa_routes(app)
- register_fulfillment_routes(app)
- register_comp_refresh_routes(app)
- register_show_prep_routes(app)
```

## Current Module Ownership

| Module | Owns |
|---|---|
| `modules/dashboard_routes.py` | Home/dashboard, Dealer Hub, events, event details, event close report, business metrics |
| `modules/inventory_routes.py` | Card list, card detail, add/edit/delete cards, duplicate/clone, storage quick update, bulk card actions, pull sheet, label preview |
| `modules/sales_routes.py` | Quick Sell, Bulk Sell, lot/deal-cart sales, payment details |
| `modules/capture_routes.py` | Mobile capture, capture upload API, image inbox, staged image cleanup |
| `modules/ai_import_routes.py` | AI image upload, AI review queue, staged card update/import/reject/delete |
| `modules/psa_routes.py` | PSA lookup, desktop scanner, mobile scanner, PSA staging flow |
| `modules/batch_routes.py` | Intake batches, active batch selection, batch detail, batch storage defaults |
| `modules/show_prep_routes.py` | Show prep loadout, selected storage locations, show prep print sheet |
| `modules/fulfillment_routes.py` | Fulfillment queue, pull/pulled/shipped/delivered workflow, bulk pulled update |
| `modules/storage_routes.py` | Storage Explorer, managed storage dropdown list, add/delete storage locations |
| `modules/comp_refresh_routes.py` | Comp refresh queue, apply/skip/clear pricing updates |
| `modules/inventory_aging.py` | Inventory aging page and aging buckets |

## Helper Ownership

| Helper | Purpose |
|---|---|
| `helpers/acquisition_helpers.py` | Acquisition calculations and ranges |
| `helpers/ai_recognition_helpers.py` | AI/card recognition support |
| `helpers/ai_review_helpers.py` | AI review/staging helper logic |
| `helpers/app_helpers.py` | Shared app-level helper functions |
| `helpers/cardsight_helpers.py` | CardSight/API-related helpers |
| `helpers/card_code_helpers.py` | Card code generation and parsing helpers |
| `helpers/deal_cart_helpers.py` | Deal cart totals and selected-card workflow |
| `helpers/image_crop_helpers.py` | Image cropping helpers |
| `helpers/image_helpers.py` | Image saving/deleting/processing utilities |
| `helpers/inventory_health_helpers.py` | Missing data/image/storage/comps health checks |
| `helpers/inventory_helpers.py` | Inventory math, totals, status calculations |
| `helpers/psa_helpers.py` | PSA scanning/lookup helper functions |
| `helpers/recognition_helpers.py` | Recognition fallback/support helpers |
| `helpers/reference_helpers.py` | Reference list/helper utilities |
| `helpers/storage_helpers.py` | Storage locations and storage summary helpers |

## Important Templates

| Template | Feature |
|---|---|
| `base.html` | Global layout, navigation, nav counts |
| `home.html` | Home launch page |
| `dealer_hub.html` | Dealer Hub |
| `dashboard.html` | Business Dashboard |
| `card_list.html` | Inventory list/table/gallery |
| `card_detail.html` | Card detail |
| `add_card.html` / `edit_card.html` | Add/edit card forms |
| `quick_sell.html` / `bulk_sell.html` | Sales workflow |
| `deal_cart.html` | Deal cart |
| `fulfillment.html` | Fulfillment queue |
| `storage.html` | Storage Explorer |
| `show_prep.html` / `show_prep_print.html` | Show Prep and print sheet |
| `events.html` / `event_detail.html` / `event_close_report.html` | Event/show management |
| `batches.html` / `batch_detail.html` | Intake batch workflow |
| `mobile_capture.html` / `image_inbox.html` | Mobile capture and image inbox |
| `ai_import_upload.html` / `ai_import_review.html` | AI import workflow |
| `psa_lookup.html` / `psa_desktop_scan.html` / `psa_mobile_scan.html` | PSA tools |
| `inventory_health.html` / `inventory_aging.html` / `comp_refresh.html` | Inventory quality and pricing tools |

## Developer Utilities

| Tool | Purpose |
|---|---|
| `tools/route_audit.py` | Scans templates for `url_for(...)` and confirms matching Flask endpoints exist |
| `tools/db_schema_audit.py` | Compares SQLAlchemy model columns against the active database schema |

## Standard Pre-Push Checks

```powershell
python tools\route_audit.py
python tools\db_schema_audit.py
python -m compileall modules helpers
git status
```

## Files/Folders To Avoid Editing

Do not patch stale copies or backups:

```text
modules/_old_placeholders/
templates/* - Copy.html
*.zip
backup folders
instance/
data/
uploads/
photos/
images/
```

## High-Risk Areas

These areas often require coordinated changes across models, routes, templates, and Render database state:

- Adding model fields
- Adding new `url_for(...)` references in templates
- Moving routes between modules
- Changing storage location behavior
- Changing intake batch behavior
- Changing event/show financial calculations
- Changing sales/fulfillment status names
- Changing image upload paths

# CardDesk Project Map

Last updated: June 10, 2026

## Core Purpose

CardDesk is a Flask app for sports card dealer inventory management. It supports inventory tracking, card intake, batch capture, AI import/review, show prep, dealer hub analytics, fulfillment, storage/location management, comps, and sales workflows.

## Core Files

- `app.py` = Main Flask application, app configuration, database initialization, route registration, and startup checks.
- `models.py` = SQLAlchemy database models including cards, dealer events, intake batches, staged imports, storage locations, image inbox records, and related workflow tables.
- `requirements.txt` = Python package dependencies for local and Render deployment.
- `.gitignore` = Keeps local-only files out of GitHub, including `.env`, virtual environments, DB files, uploads, images, patch ZIPs, and backup folders.
- `static/css/carddesk.css` = Main application styling.
- `templates/base.html` = Main layout, top navigation, shared page shell, nav count JavaScript.

## Important Folders

- `modules/` = Flask route files grouped by feature area.
- `helpers/` = Shared business logic and utility functions used by route modules.
- `templates/` = HTML templates.
- `static/` = CSS, uploads, and static assets.
- `tools/` = Local developer utilities such as route audit and DB schema audit.
- `modules/_old_placeholders/` = Old placeholder route files. Do not patch these.

## Current Route Registration

`app.py` should register the active route modules. If a page suddenly reports a missing endpoint, check that the matching module is imported and registered.

Expected route registration areas include:

- Dashboard / Dealer Hub / Events
- Inventory
- Sales
- Capture / Image Inbox
- AI Import
- PSA tools
- Fulfillment
- Storage
- Comps
- Show Prep / Event loadout
- Inventory Aging
- Intake Batches

## Routes / Modules

### `modules/dashboard_routes.py`

Owns:

- Home / Dealer Hub entry points
- Business Dashboard
- Dealer Hub metrics
- Events / Show History
- Event Detail
- Event Close Report
- Start / close event workflows
- Event expenses
- Event statistics and financial summaries
- Recent sales and recent acquisitions widgets
- Dashboard action links

Templates:

- `home.html`
- `dealer_hub.html`
- `dashboard.html`
- `events.html`
- `event_detail.html`
- `event_close_report.html`

Common endpoints:

- `home`
- `dealer_hub`
- `dashboard`
- `events`
- `create_event`
- `event_detail`
- `event_close_report`
- `start_existing_event`
- `close_event`
- `update_event_expenses`
- `nav_counts`

### `modules/inventory_routes.py`

Owns:

- Card List
- Card Detail
- Add Card
- Edit Card
- Delete Card
- Clone Card
- Add Duplicate
- Status updates
- Storage updates from card list
- Bulk inventory actions
- Bulk delete route used by card list
- Pull sheet / label preview if kept in inventory module
- Inventory filters including status, collection type, storage, acquisition source, acquisition event, sold range, acquisition range, and advanced filters

Templates:

- `card_list.html`
- `card_detail.html`
- `add_card.html`
- `edit_card.html`
- `pull_sheet.html`
- `label_preview.html`

Common endpoints:

- `cards`
- `card_detail`
- `add_card`
- `edit_card`
- `delete_card`
- `clone_card`
- `add_duplicate`
- `update_card_status`
- `update_card_storage`
- `bulk_delete_cards`
- `label_preview`
- `pull_sheet`

### `modules/sales_routes.py`

Owns:

- Quick Sell
- Bulk Sell
- Deal Cart
- Add/remove cards from deal cart
- Clear deal cart
- Sell deal cart as lot
- Sold card processing
- Payment type saving
- Fulfillment status initialization after sale

Templates:

- `quick_sell.html`
- `bulk_sell.html`
- `deal_cart.html`

Common endpoints:

- `quick_sell`
- `bulk_sell`
- `deal_cart`
- `add_to_deal_cart`
- `remove_from_deal_cart`
- `clear_deal_cart`

### `modules/capture_routes.py`

Owns:

- Mobile Capture
- Camera capture workflow
- Auto-save behavior
- Captured image staging
- Image Inbox
- Uploaded image serving
- Delete unused image inbox item
- Active batch awareness during capture
- Update active batch storage from mobile capture

Templates:

- `mobile_capture.html`
- `image_inbox.html`

Common endpoints:

- `mobile_capture`
- `mobile_capture_upload`
- `uploaded_file`
- `image_inbox`
- `delete_image_inbox_item`
- `update_intake_batch_storage`

### `modules/ai_import_routes.py`

Owns:

- AI Import Upload
- AI Review Queue
- Staged card review
- Update staged import
- Reject staged import
- Delete staged import
- Import approval into inventory
- Duplicate warnings
- Batch association during AI review/import

Templates:

- `ai_import_upload.html`
- `ai_import_review.html`

Common endpoints:

- `ai_import_upload`
- `ai_import_review`
- `update_staged_import`
- `reject_staged_import`
- `delete_staged_import`

### `modules/psa_routes.py`

Owns:

- PSA Lookup
- Desktop PSA Scanner
- Mobile PSA Scanner
- PSA cert lookup / scanner input
- PSA staging workflow into AI review

Templates:

- `psa_lookup.html`
- `psa_desktop_scan.html`
- `psa_mobile_scan.html`

Common endpoints:

- `psa_lookup`
- `psa_desktop_scan`
- `psa_mobile_scan`

### `modules/show_prep_routes.py`

Owns:

- Show Prep page
- Event loadouts
- Show location selection
- Loadout storage checkboxes
- Show badge toggling
- Show Prep Print / Loadout Sheet
- Show-only checklist filtering
- Pre-show problem counts for loaded locations only

Templates:

- `show_prep.html`
- `show_prep_print.html`

Common endpoints:

- `show_prep`
- `show_prep_print`

### `modules/fulfillment_routes.py`

Owns:

- Fulfillment Queue
- Pulling cards
- Mark selected as pulled
- Shipping workflow
- Ready to Ship / Shipped / Delivered workflow
- Fulfillment status updates
- Pull sheet links for fulfillment views

Templates:

- `fulfillment.html`

Common endpoints:

- `fulfillment_queue`
- `update_fulfillment_status`
- `mark_selected_fulfillment_pulled`

### `modules/storage_routes.py`

Owns:

- Storage Explorer
- Managed storage location dropdown values
- Add storage location
- Delete storage location
- Missing storage links
- Storage summary counts

Templates:

- `storage.html`

Common endpoints:

- `storage_explorer`
- `add_storage_location`
- `delete_storage_location`

### `modules/comp_refresh_routes.py`

Owns:

- Comp refresh page
- Pricing refresh tools
- Apply comp update
- Apply all
- Skip comp item
- Clear comp queue

Templates:

- `comp_refresh.html`

Common endpoints:

- `comp_refresh`
- `comp_refresh_run`
- `comp_refresh_apply`
- `comp_refresh_apply_all`
- `comp_refresh_skip`
- `comp_refresh_clear`

### `modules/inventory_aging.py` or `modules/inventory_aging_routes.py`

Owns:

- Inventory Aging page
- Aging buckets
- Stale inventory calculations
- Event/show loadout aging filter
- Inventory aging links from dashboard and show prep

Templates:

- `inventory_aging.html`

Common endpoints:

- `inventory_aging`

### Intake Batch Routes

Depending on the current layout, intake batch routes may live in `capture_routes.py`, `inventory_routes.py`, or a dedicated batch/intake route module.

Owns:

- Batch list
- Batch detail
- Create intake batch
- Activate/reopen batch
- Close batch
- Update batch metadata
- Update default storage location
- Show active batch on AI Review and Mobile Capture
- Associate captured/imported cards with batch
- Display batch name on card detail

Templates:

- `batches.html`
- `batch_detail.html`

Common endpoints:

- `intake_batches`
- `intake_batch_detail`
- `create_intake_batch`
- `activate_intake_batch`
- `close_intake_batch`
- `update_intake_batch`
- `update_intake_batch_storage`

## Helpers

### `helpers/inventory_helpers.py`

Used for:

- Inventory calculations
- Totals and summaries
- Inventory filters
- Active inventory logic
- Cost/value/profit calculations

### `helpers/ai_import_helpers.py`

Used for:

- AI review/import workflow logic
- Staged card processing
- Duplicate detection support
- Import-to-card conversion

### `helpers/ai_recognition_helpers.py`

Used for:

- Image recognition support
- AI card recognition/parsing helpers

### `helpers/app_helpers.py`

Used for:

- Shared app utilities
- Formatting helpers
- Common template support

### `helpers/storage_helpers.py`

Used for:

- Managed storage locations
- Storage summary helpers
- Missing storage counts
- Storage dropdown support

### Other Helpers

If more helper files exist, keep business logic there instead of duplicating it inside route modules.

## Templates By Feature

### Main Layout

- `base.html` = Top nav, shared CSS/JS links, nav counts
- `home.html` = Landing page / launch cards

### Dealer / Dashboard / Events

- `dealer_hub.html`
- `dashboard.html`
- `events.html`
- `event_detail.html`
- `event_close_report.html`

### Inventory

- `card_list.html`
- `card_detail.html`
- `add_card.html`
- `edit_card.html`
- `pull_sheet.html`
- `label_preview.html`

### Sales

- `quick_sell.html`
- `bulk_sell.html`
- `deal_cart.html`

### Intake / Capture / AI

- `intake_tools.html`
- `mobile_capture.html`
- `image_inbox.html`
- `ai_import_upload.html`
- `ai_import_review.html`
- `batches.html`
- `batch_detail.html`

### PSA

- `psa_lookup.html`
- `psa_desktop_scan.html`
- `psa_mobile_scan.html`

### Show Prep

- `show_prep.html`
- `show_prep_print.html`

### Fulfillment

- `fulfillment.html`

### Storage

- `storage.html`

### Comps / Aging / Health

- `comp_refresh.html`
- `inventory_aging.html`
- `inventory_health.html`

## Developer Tools

### `tools/route_audit.py`

Purpose:

- Scans templates for `url_for(...)`.
- Loads the Flask app.
- Compares template endpoints against registered Flask endpoints.
- Reports missing routes before deployment.

Run:

```powershell
python tools\route_audit.py
```

Good result:

```text
PASS: No missing template routes found.
```

Use before:

```powershell
git push origin main
```

### `tools/db_schema_audit.py`

Purpose:

- Compares SQLAlchemy model columns against actual database columns.
- Reports missing or extra columns.
- Read-only.
- Useful before Render deploys when models changed.

Run:

```powershell
python tools\db_schema_audit.py
```

## When I Need To Change...

### Change top menu / navigation

- `templates/base.html`
- Possibly `nav_counts` route in dashboard/app module

### Change Dealer Hub

- `templates/dealer_hub.html`
- `modules/dashboard_routes.py`
- Dashboard/helper functions if metrics change

### Change Business Dashboard

- `templates/dashboard.html`
- `modules/dashboard_routes.py`
- Inventory/stat helper functions if totals change

### Change Event creation / Show History

- `templates/events.html`
- `modules/dashboard_routes.py`
- `models.py` if event fields change

### Change Event Detail / Expenses

- `templates/event_detail.html`
- `modules/dashboard_routes.py`
- `models.py` if new event expense fields are added

### Change Event Close Report

- `templates/event_close_report.html`
- `modules/dashboard_routes.py`

### Change Show Prep / Loadout

- `templates/show_prep.html`
- `templates/show_prep_print.html`
- `modules/show_prep_routes.py`
- Storage/helper functions if location filtering changes

### Change scanner behavior

- `templates/psa_desktop_scan.html`
- `templates/psa_mobile_scan.html`
- `modules/psa_routes.py`

### Change mobile capture

- `templates/mobile_capture.html`
- `modules/capture_routes.py`
- `templates/image_inbox.html` if image inbox behavior changes

### Change AI Review

- `templates/ai_import_review.html`
- `templates/ai_import_upload.html`
- `modules/ai_import_routes.py`
- `helpers/ai_import_helpers.py`

### Change Card Intake Tools

- `templates/intake_tools.html`
- `modules/capture_routes.py`
- PSA / AI / batch route modules depending on the link or workflow

### Change Intake Batches

- `templates/batches.html`
- `templates/batch_detail.html`
- Intake batch route functions
- `models.py` if batch fields change
- `templates/mobile_capture.html` if active batch capture changes
- `templates/ai_import_review.html` if batch import display changes
- `templates/card_detail.html` if batch display changes

### Change card list

- `templates/card_list.html`
- `modules/inventory_routes.py`
- `helpers/inventory_helpers.py`

### Change card details page

- `templates/card_detail.html`
- `modules/inventory_routes.py`

### Change Add/Edit Card

- `templates/add_card.html`
- `templates/edit_card.html`
- `modules/inventory_routes.py`
- `models.py` if fields change
- `modules/storage_routes.py` or `helpers/storage_helpers.py` if dropdown values change

### Change storage dropdown/location system

- `templates/add_card.html`
- `templates/edit_card.html`
- `templates/card_list.html`
- `templates/mobile_capture.html`
- `templates/batch_detail.html`
- `templates/storage.html`
- `modules/storage_routes.py`
- `modules/inventory_routes.py`
- `modules/capture_routes.py`
- Intake batch routes
- `helpers/storage_helpers.py`
- `models.py` if storage table/fields change

### Change Quick Sell

- `templates/quick_sell.html`
- `modules/sales_routes.py`
- `models.py` if sale/payment fields change

### Change Deal Cart

- `templates/deal_cart.html`
- `modules/sales_routes.py`
- `helpers/deal_cart_helpers.py` if present

### Change payment methods

- `templates/quick_sell.html`
- `templates/bulk_sell.html`
- `templates/edit_card.html`
- `modules/sales_routes.py`
- `modules/inventory_routes.py`
- `models.py` if payment fields change

### Change fulfillment

- `templates/fulfillment.html`
- `modules/fulfillment_routes.py`
- `templates/card_list.html` if status shortcuts change
- `templates/dealer_hub.html` or `dashboard.html` if action counts change

### Change comps

- `templates/comp_refresh.html`
- `modules/comp_refresh_routes.py`
- Comp helper/model functions if present

### Change inventory aging

- `templates/inventory_aging.html`
- Inventory aging route module
- Dashboard/show prep links if aging counts change

### Change inventory health

- `templates/inventory_health.html`
- Inventory health route/helper module if present
- `templates/base.html` if nav badge changes

### Change styling

- `static/css/carddesk.css`
- Inline styles inside templates only when necessary; prefer central CSS.

## Deployment / Git Workflow

Before committing:

```powershell
python -m compileall modules helpers
python tools\route_audit.py
python tools\db_schema_audit.py
git status
```

Commit and push:

```powershell
git add .
git commit -m "Describe changes"
git push origin main
```

Render:

- Confirm repo is `BTCDynamics/carddesk`.
- Confirm branch is `main`.
- If weird old behavior continues, use Manual Deploy > Clear build cache & deploy.
- If local works but Render fails with `no such column` or `no such table`, run the DB schema audit locally and check whether Render needs a safe migration/update block.

## Common Problems And Checks

### Page crashes with `BuildError` / missing endpoint

Likely cause:

- Template references `url_for('some_endpoint')`, but no matching route is registered.

Check:

```powershell
python tools\route_audit.py
```

Fix:

- Add the missing route function.
- Or correct the template endpoint name.
- Or make sure the module containing the route is imported and registered in `app.py`.

### Local works but Render crashes

Likely causes:

- Render deployed an older commit.
- Render is on the wrong branch.
- Build cache is stale.
- Render database schema is older than local database.
- Local files were restored from a ZIP but not pushed.

Check:

```powershell
git status
git log --oneline -5
git remote -v
python tools\route_audit.py
python tools\db_schema_audit.py
```

### Storage dropdown missing somewhere

Check:

- `add_card.html`
- `edit_card.html`
- `card_list.html`
- `mobile_capture.html`
- `batch_detail.html`
- `ai_import_review.html`
- `storage.html`
- `helpers/storage_helpers.py`
- route context variables supplying storage locations

### Batch not showing on card detail

Check:

- `models.py` for batch relationship / foreign key field.
- AI import route that creates the card.
- Mobile capture / batch association logic.
- `templates/card_detail.html`.

### Show Prep counts wrong

Check:

- Active event/loadout locations.
- Show Prep route filtering.
- Inventory Aging route if linked from Show Prep.
- Make sure problem rows count only loaded locations, not all inventory.

## Notes

Always patch the current file version. Avoid using old copies such as:

- `dealer_hub - Copy.html`
- `app - Copy.py`
- files in `modules/_old_placeholders/`
- old extracted ZIP folders
- old CardWatch folders

When uploading for patch work, ZIP the current folder:

```powershell
Compress-Archive -Path C:\apps\carddesk\* -DestinationPath C:\apps\carddesk-current.zip -Force
```

Do not commit:

- `.env`
- `.venv/` or `venv/`
- SQLite DB files
- `instance/`
- `uploads/`
- `photos/`
- `images/`
- generated patch ZIP files
- API token text files

Run the audit utilities before every push after template, route, or model changes.

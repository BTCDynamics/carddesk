# CardDesk Features

_Last updated: 2026-06-10_

## Inventory Management

CardDesk stores sports card inventory with player, sport, brand, year, card number, variation, card type, HOF/rookie flags, grading details, cost, estimated value, asking price, status, storage location, images, and batch/event context.

Key files:

```text
modules/inventory_routes.py
templates/card_list.html
templates/card_detail.html
templates/add_card.html
templates/edit_card.html
models.py
```

## Storage Management

Managed storage locations drive dropdowns across add/edit/rapid entry/AI review/batch/mobile capture workflows.

Key files:

```text
modules/storage_routes.py
helpers/storage_helpers.py
templates/storage.html
```

## Sales Workflow

Supports Quick Sell, Bulk Sell, deal cart lot sale, sold price/date/platform/payment details, and profit/loss tracking.

Key files:

```text
modules/sales_routes.py
templates/quick_sell.html
templates/bulk_sell.html
templates/deal_cart.html
```

## Fulfillment

Tracks sold cards through pulling, pulled, ready to ship, shipped, and delivered.

Key files:

```text
modules/fulfillment_routes.py
templates/fulfillment.html
templates/pull_sheet.html
```

## Dealer Hub

Operational command center for dealer activity, events, recent acquisitions, recent sales, show prep, and work-needed queues.

Key files:

```text
modules/dashboard_routes.py
templates/dealer_hub.html
```

## Business Dashboard

Analytics and business metrics for inventory value, costs, sales, profit/loss, health signals, allocations, and aging signals.

Key files:

```text
modules/dashboard_routes.py
templates/dashboard.html
```

## Events / Shows

Create, start, manage, close, and report on dealer events/shows, including table fee and expenses.

Key files:

```text
modules/dashboard_routes.py
templates/events.html
templates/event_detail.html
templates/event_close_report.html
models.py
```

## Show Prep

Select storage locations for an event loadout, flag show locations, print loadout sheets, and limit stale/cost/comps checks to selected show inventory.

Key files:

```text
modules/show_prep_routes.py
templates/show_prep.html
templates/show_prep_print.html
```

## Intake Batches

Create named intake batches with default storage location and batch context. Batches connect mobile capture, AI review, and imported cards.

Key files:

```text
modules/batch_routes.py
templates/batches.html
templates/batch_detail.html
models.py
```

## Mobile Capture

Mobile-friendly camera capture workflow for card images, with active batch awareness and image inbox support.

Key files:

```text
modules/capture_routes.py
templates/mobile_capture.html
templates/image_inbox.html
```

## AI Import

Upload card images, review AI-recognized card data, check duplicates, assign storage, and import staged cards into inventory.

Key files:

```text
modules/ai_import_routes.py
helpers/ai_review_helpers.py
helpers/ai_recognition_helpers.py
templates/ai_import_upload.html
templates/ai_import_review.html
models.py
```

## PSA Tools

Manual PSA lookup, desktop scanner, and mobile scanner workflows for graded card intake.

Key files:

```text
modules/psa_routes.py
helpers/psa_helpers.py
templates/psa_lookup.html
templates/psa_desktop_scan.html
templates/psa_mobile_scan.html
```

## Inventory Health

Find inventory issues such as missing images, missing storage locations, stale values, incomplete fields, and review-needed cards.

Key files:

```text
helpers/inventory_health_helpers.py
templates/inventory_health.html
```

## Inventory Aging

Aging buckets and stale inventory review, including event/show-scoped filtering.

Key files:

```text
modules/inventory_aging.py
templates/inventory_aging.html
```

## Comp Refresh

Queue and apply market comp/price updates.

Key files:

```text
modules/comp_refresh_routes.py
templates/comp_refresh.html
models.py
```

## Developer Safety Utilities

Route audit catches template/endpoint mismatches. DB audit catches model/database schema drift.

Key files:

```text
tools/route_audit.py
tools/db_schema_audit.py
docs/
```

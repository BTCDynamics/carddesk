# CardDesk Project Map

## Core Files
- app.py = Main Flask application and route registration.
- models.py = Database models (Card, DealerEvent, staging/import records, etc.).
- static/css/carddesk.css = Main application styling.

## Routes (modules)

### dashboard_routes.py
Owns:
- Dealer Hub
- Business Dashboard
- Events
- Event Detail
- Event Close Report
- Event statistics and financial summaries

Templates:
- dealer_hub.html
- dashboard.html
- events.html
- event_detail.html
- event_close_report.html

### inventory_routes.py
Owns:
- Card List
- Card Detail
- Add Card
- Edit Card
- Delete Card
- Bulk inventory actions

Templates:
- card_list.html
- card_detail.html
- add_card.html
- edit_card.html

### sales_routes.py
Owns:
- Quick Sell
- Bulk Sell
- Sold card processing
- Payment type saving

Templates:
- quick_sell.html
- bulk_sell.html

### capture_routes.py
Owns:
- Mobile Capture
- Camera capture workflow
- Staging captured images

Templates:
- mobile_capture.html

### ai_import_routes.py
Owns:
- AI Review Queue
- AI Import Approval
- Staged card review

Templates:
- ai_import_review.html
- ai_import_upload.html

### psa_routes.py
Owns:
- PSA Lookup
- Desktop PSA Scanner
- Mobile PSA Scanner
- PSA staging workflow

Templates:
- psa_lookup.html
- psa_desktop_scan.html

### show_prep_routes.py
Owns:
- Show Prep
- Event loadouts
- Show location selection

Templates:
- show_prep.html

### fulfillment_routes.py
Owns:
- Pulling cards
- Shipping workflow
- Delivered/Completed workflow

Templates:
- fulfillment.html

### storage_routes.py
Owns:
- Storage Explorer
- Storage Locations
- Location maintenance

Templates:
- storage.html

### comp_refresh_routes.py
Owns:
- Comp updates
- Pricing refresh tools

Templates:
- comp_refresh.html

### inventory_aging.py
Owns:
- Inventory Aging page
- Aging calculations

Templates:
- inventory_aging.html

## Helpers

helpers/
- inventory_helpers.py = inventory calculations and utilities
- ai_import_helpers.py = AI review/import logic
- ai_recognition_helpers.py = image recognition support
- app_helpers.py = shared helper functions
- storage_helpers.py = storage/location utilities

## When I Need To Change...

Change top menu:
- templates/base.html

Change Dealer Hub:
- templates/dealer_hub.html
- modules/dashboard_routes.py

Change Event calculations:
- modules/dashboard_routes.py

Change Event report:
- templates/event_close_report.html
- modules/dashboard_routes.py

Change scanner behavior:
- templates/psa_desktop_scan.html
- modules/psa_routes.py

Change mobile capture:
- templates/mobile_capture.html
- modules/capture_routes.py

Change AI Review:
- templates/ai_import_review.html
- modules/ai_import_routes.py

Change card details page:
- templates/card_detail.html
- modules/inventory_routes.py

Change Quick Sell:
- templates/quick_sell.html
- modules/sales_routes.py

Change payment methods:
- templates/quick_sell.html
- templates/edit_card.html
- modules/sales_routes.py
- modules/inventory_routes.py

Change styling:
- static/css/carddesk.css

## Notes
Always patch the current file version. Avoid using old copies such as:
- dealer_hub - Copy.html
- files in modules/_old_placeholders/

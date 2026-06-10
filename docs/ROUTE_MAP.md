# CardDesk Route Map

_Last updated: 2026-06-10_

Routes discovered from `app.py` and `modules/*.py`.

## app.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/api/nav-counts` | `nav_counts` |
| `GET` | `/intake-tools` | `intake_tools` |
| `GET` | `/static/uploads/<path:filename>` | `uploaded_static_file` |
| `GET` | `/uploads/<path:filename>` | `uploaded_file` |

## modules/ai_import_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET,POST` | `/ai-import` | `ai_import_upload` |
| `POST` | `/ai-import/<int:staging_id>/delete` | `delete_staged_import` |
| `POST` | `/ai-import/<int:staging_id>/import` | `import_staged_card` |
| `POST` | `/ai-import/<int:staging_id>/reject` | `reject_staged_import` |
| `POST` | `/ai-import/<int:staging_id>/update` | `update_staged_import` |
| `GET` | `/ai-import/review` | `ai_import_review` |

## modules/batch_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/intake-batches` | `intake_batches` |
| `GET` | `/intake-batches/<int:batch_id>` | `intake_batch_detail` |
| `POST` | `/intake-batches/<int:batch_id>/activate` | `activate_intake_batch` |
| `POST` | `/intake-batches/<int:batch_id>/close` | `close_intake_batch` |
| `POST` | `/intake-batches/<int:batch_id>/update` | `update_intake_batch` |
| `POST` | `/intake-batches/<int:batch_id>/update-storage` | `update_intake_batch_storage` |
| `POST` | `/intake-batches/create` | `create_intake_batch` |

## modules/capture_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/image-inbox` | `image_inbox` |
| `POST` | `/image-inbox/<int:image_id>/delete` | `delete_image_inbox_item` |
| `GET` | `/mobile-capture` | `mobile_capture` |
| `POST` | `/mobile-capture/upload` | `mobile_capture_upload` |

## modules/comp_refresh_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/comp-refresh` | `comp_refresh` |
| `POST` | `/comp-refresh/<int:item_id>/apply` | `comp_refresh_apply` |
| `POST` | `/comp-refresh/<int:item_id>/skip` | `comp_refresh_skip` |
| `POST` | `/comp-refresh/apply-all` | `comp_refresh_apply_all` |
| `POST` | `/comp-refresh/clear` | `comp_refresh_clear` |
| `POST` | `/comp-refresh/run` | `comp_refresh_run` |

## modules/dashboard_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/` | `home` |
| `GET` | `/dashboard` | `dashboard` |
| `GET` | `/dealer-hub` | `dealer_hub` |
| `GET` | `/events` | `events` |
| `GET` | `/events/<int:event_id>` | `event_detail` |
| `POST` | `/events/<int:event_id>/close` | `close_event` |
| `GET` | `/events/<int:event_id>/close-report` | `event_close_report` |
| `POST` | `/events/<int:event_id>/expenses` | `update_event_expenses` |
| `POST` | `/events/<int:event_id>/start` | `start_existing_event` |
| `POST` | `/events/create` | `create_event` |
| `POST` | `/events/start` | `create_event` |

## modules/fulfillment_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/fulfillment` | `fulfillment_queue` |
| `POST` | `/fulfillment/<int:card_id>/status` | `update_fulfillment_status` |
| `POST` | `/fulfillment/mark-selected-pulled` | `mark_selected_fulfillment_pulled` |

## modules/inventory_aging.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/inventory-aging` | `inventory_aging` |

## modules/inventory_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET,POST` | `/add-card` | `add_card` |
| `GET` | `/cards` | `cards` |
| `GET` | `/cards/<int:card_id>` | `card_detail` |
| `POST` | `/cards/<int:card_id>/add-duplicate` | `add_duplicate` |
| `GET` | `/cards/<int:card_id>/clone` | `clone_card` |
| `POST` | `/cards/<int:card_id>/delete` | `delete_card` |
| `GET,POST` | `/cards/<int:card_id>/edit` | `edit_card` |
| `POST` | `/cards/<int:card_id>/update-status` | `update_card_status` |
| `POST` | `/cards/<int:card_id>/update-storage` | `update_card_storage` |
| `POST` | `/cards/bulk-delete` | `bulk_delete_cards` |
| `GET` | `/inventory-aging` | `inventory_aging` |
| `POST` | `/labels/preview` | `label_preview` |
| `GET,POST` | `/rapid-entry` | `rapid_entry` |

## modules/psa_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET,POST` | `/psa-desktop-scan` | `psa_desktop_scan` |
| `GET,POST` | `/psa-lookup` | `psa_lookup` |
| `GET,POST` | `/psa-mobile-scan` | `psa_mobile_scan` |

## modules/sales_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `POST` | `/bulk-sell` | `bulk_sell` |
| `GET,POST` | `/cards/<int:card_id>/quick-sell` | `quick_sell` |
| `GET` | `/deal-cart` | `deal_cart` |
| `POST` | `/deal-cart/add` | `add_to_deal_cart` |
| `POST` | `/deal-cart/clear` | `clear_deal_cart` |
| `POST` | `/deal-cart/remove/<int:card_id>` | `remove_from_deal_cart` |

## modules/show_prep_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET,POST` | `/show-prep` | `show_prep` |
| `GET` | `/show-prep/print` | `show_prep_print` |

## modules/storage_routes.py

| Methods | URL Rule | Endpoint Function |
|---|---|---|
| `GET` | `/health` | `health` |
| `GET` | `/inventory-health` | `inventory_health` |
| `GET` | `/pull-sheet` | `pull_sheet` |
| `GET` | `/storage` | `storage_explorer` |
| `POST` | `/storage/add-location` | `add_storage_location` |
| `POST` | `/storage/delete-location` | `delete_storage_location` |

## Route Audit

Run this before every commit/push:

```powershell
python tools\route_audit.py
```

A good result:

```text
PASS: No missing template routes found.
```

If the audit fails, it means a template contains `url_for('some_endpoint')` but Flask does not have a registered endpoint with that function name.

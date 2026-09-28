# Phase 3.6: Flutter Hierarchy Integration Report

## 1. Existing Flutter Hierarchy Behavior
Prior to Phase 3.6, the GramSevak Flutter farmer application (`farmer_app`) had several hierarchy limitations:
- Hardcoded defaults: `DistrictItem.fromJson` defaulted to 'Nashik', `BlockItem.fromJson` defaulted to 'Baglan', and `PanchayatItem.fromJson` defaulted to 'Nashik' and 'Baglan'.
- Incomplete response parsing: `FarmerRepository.getDistricts()` and `FarmerRepository.getDistrictBlocks()` expected a raw JSON `List` rather than the Phase 3.4 paginated envelope (`total`, `page`, `page_size`, `total_pages`, `items`), falling back to static mock items during live calls.
- Flat Panchayat selection: The picker did not strictly enforce progressive parent-child unlocking or propagate server-side pagination across all tiers.
- In-flight request race vulnerability: Rapid user interaction or breadcrumb switching could allow an older asynchronous response from an earlier selection to overwrite newer data.

## 2. New District → Block → Panchayat Flow
The hierarchy picker in `panchayat_picker_sheet.dart` was re-engineered around a clean 3-step progressive navigation pattern:
1. **District Selection (Step 1)**: Farmer selects an administrative district from the paginated backend list.
2. **Block Selection (Step 2)**: Unlocked only after a District is selected; queries blocks strictly partitioned by `district_id`.
3. **Panchayat Selection (Step 3)**: Unlocked only after a Block is selected; queries Panchayats strictly belonging to `block_id`.
4. **Context Propagation**: Tapping a Panchayat invokes `widget.onSelect(panchayat)`, updates the active village in `main.dart`, and reloads the downscaled weather forecast and agromet advisory.

Strict dependency invalidation rules:
- Changing District: resets selected Block (`null`) and selected Panchayat (`null`), clears child lists, resets child search and pagination to page 1, and invalidates in-flight child requests.
- Changing Block: resets selected Panchayat (`null`), clears Panchayat list, resets search and pagination to page 1, and invalidates in-flight Panchayat requests.

## 3. API Integration
The network layer was extended through `FarmerApiClient` and `FarmerRepository` to consume Phase 3.3/3.4 REST endpoints:
- `GET /api/v1/districts?page={page}&page_size={pageSize}&search={search}` via `getDistricts()` and alias `listDistricts()`.
- `GET /api/v1/districts/{districtId}/blocks?page={page}&page_size={pageSize}&search={search}` via `getDistrictBlocks()` and alias `listBlocks()`.
- `GET /api/v1/blocks/{blockId}/panchayats?page={page}&page_size={pageSize}&search={search}` via `getBlockPanchayats()` and alias `listPanchayats()`.
- `GET /api/v1/panchayats/{panchayatId}` via `getPanchayatById()` and alias `getPanchayat()`.

All endpoints use `FarmerApiClient.defaultBaseUrl` (defaulting to the deployed HTTPS backend `https://gramseva-0etv.onrender.com/api/v1` configurable via `--dart-define=API_BASE_URL=...`). Timeout duration was increased to 15s to withstand rural 3G/4G connectivity. Zero secrets or service-role keys are exposed in client builds.

## 4. Data Models
Strongly typed models were created and updated in `hierarchy_models.dart` and `panchayat_item.dart`:
- `DistrictItem`: `id`, `name`, `code`, `state` (no hardcoded 'Nashik' default).
- `DistrictPagination`: `total`, `page`, `pageSize`, `totalPages`, `items`.
- `BlockItem`: `id`, `districtId`, `name`, `code` (no hardcoded 'Baglan' default).
- `BlockPagination`: `total`, `page`, `pageSize`, `totalPages`, `items`.
- `PanchayatItem`: `panchayatId`, `lgdCode`, `panchayatName`, `blockName`, `districtName`, `latitude`, `longitude`, `elevationM` (supports both flat and nested parent objects).
- `PanchayatPagination`: `total`, `page`, `pageSize`, `totalPages`, `items`.

## 5. Repository/Service Integration
`FarmerRepository` coordinates data access and error mapping:
- Translates JSON payloads into typed pagination containers.
- Safely handles API errors, throwing `FarmerApiException` with status codes.
- Maintains static `fallbackPanchayats` for offline resilience when network connectivity is lost entirely.
- Exposes standard method names and section-mandated aliases (`listDistricts`, `listBlocks`, `listPanchayats`, `getPanchayat`).

## 6. State-Management Approach
State management adheres strictly to idiomatic Flutter `StatefulWidget` patterns without adding unneeded third-party libraries:
- Isolated per-step state variables:
  - District: `_districts`, `_selectedDistrict`, `_districtPage`, `_districtTotalPages`, `_districtTotal`, `_districtSearch`, `_loadingDistricts`, `_districtError`.
  - Block: `_blocks`, `_selectedBlock`, `_blockPage`, `_blockTotalPages`, `_blockTotal`, `_blockSearch`, `_loadingBlocks`, `_blockError`.
  - Panchayat: `_panchayats`, `_selectedPanchayat`, `_panchayatPage`, `_panchayatTotalPages`, `_panchayatTotal`, `_panchayatSearch`, `_loadingPanchayats`, `_panchayatError`.
- Stepper mode `PickerStep` toggles active view and dynamic header breadcrumbs.

## 7. Pagination
Server-side pagination parameters (`page`, `page_size`) and backend envelope metadata (`total`, `total_pages`) are integrated:
- Page size bounds: 20 items for Districts and Blocks; 50 items for Panchayats.
- Dynamic pagination bar displays `Page X of Y (Total Z)` with Prev and Next buttons.
- Buttons are disabled on boundary pages (`page <= 1` or `page >= totalPages`).
- Automatic resets: search query changes reset page to 1; parent selection changes reset child page to 1.
- No client-side array slicing or unbounded bulk downloads.

## 8. Search
Server-side debounced search is active across all three levels:
- Input changes trigger a 250ms debounce window using a single `Timer`.
- When debounced timer fires, the search parameter is transmitted directly to the backend.
- Changing search query resets pagination to page 1.

## 9. Async Race-Condition Handling
Monotonically increasing sequence counters guard against out-of-order asynchronous responses:
- `_districtReqId`, `_blockReqId`, `_panchayatReqId`.
- Each initiated request captures its sequence token (`final reqId = ++_...ReqId;`).
- When response arrives, it is discarded if `reqId != _...ReqId` or if the widget is no longer mounted.
- Switching parent selections immediately cancels reliance on in-flight child requests.

## 10. Forecast Integration
Upon Panchayat selection:
- `PanchayatItem` is passed to `main.dart`.
- `_selectedPanchayatId` is updated.
- `_reloadForecast()` is dispatched, fetching downscaled weather and verified advisory for the new Panchayat.
- The ML downscaling models, backend inference algorithms, and advisory rules remain completely unmodified.

## 11. Persistence Behavior
- Existing runtime state preservation in `main.dart` was maintained.
- If a farmer selects a village outside the initial pilot list, it is dynamically prepended to `_panchayats` so UI references remain stable.

## 12. Responsive Behavior
- Follows the Universal Farmer Product Design System.
- Tested on standard and compact screen heights with `ConstrainedBox` limits (`maxHeight: MediaQuery.of(context).size.height * 0.38`).
- Bounded touch targets (min height 48px) and non-overflowing text with `TextOverflow.ellipsis`.

## 13. Accessibility
- All interactive elements use `Semantics(button: true, label: ...)` or semantic Flutter controls.
- Ink splash effects and tap feedback comply with Material Design guidelines via transparent `Material` wrappers.
- High-contrast selection borders (`AppColors.primary500`, width 1.5) and badges (`AppColors.primary050`).

## 14. Production Configuration
- Production requests target HTTPS deployed Render backend (`https://gramseva-0etv.onrender.com/api/v1`).
- Configurable via `--dart-define=API_BASE_URL=...` for testing or custom environments.
- Zero credentials or service-role keys are baked into the binary.

## 15. Testing Performed
- **Static Analysis (`flutter analyze`)**: 0 issues found (clean pass).
- **Unit & Widget Tests (`flutter test`)**: **32/32 tests passed**:
  - `test/hierarchy_integration_test.dart` (14 tests): Models, pagination, mock repository, 3-step navigation, parent reset, debounced search, error recovery.
  - `test/real_backend_hierarchy_test.dart` (7 tests): Live backend queries against Supabase database (Districts, Nashik blocks, Pune blocks isolation, Baglan 132 Panchayats, search, single detail, forecast).
  - `test/farmer_api_integration_test.dart` (10 tests): Forecast parsing, advisory verification rules, offline fallback.
  - `test/widget_test.dart` (1 test): App shell rendering.
- **Formatting (`dart format`)**: All modified files formatted to Dart standard.

## 16. Known Limitations
- Background periodic sync or SQLite caching for administrative hierarchy in Flutter is deferred to Phase 3.7.

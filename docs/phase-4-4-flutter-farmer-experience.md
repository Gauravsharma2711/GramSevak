# Phase 4.4: Flutter Farmer Onboarding + Home Experience

## 1. Overview
Phase 4.4 redesigns the GramSevak Flutter farmer application's onboarding, Panchayat selection, and home experience using the Universal Farmer Product Design System, Phase 4.1 UX architecture, and Phase 3.6 administrative hierarchy.

The redesigned experience delivers:
- Calm, agricultural visual tone with restrained typography.
- Short, friendly 3-step visual onboarding story.
- Direct integration of Phase 3.6 District → Block → Panchayat picker.
- Clutter-free home screen highlighting today's localized rainfall forecast and actionable agromet advisory.
- Custom vector micro-illustrations (`CustomPainter`) and subtle audio playback waveforms.

---

## 2. Onboarding Experience
Created `FarmerOnboardingScreen` (`farmer_app/lib/screens/onboarding_screen.dart`):
1. **Welcome Screen**:
   - Focus: Introduces village-level downscaled rain & weather for farms.
   - Visual: Custom vector `AgriSunFieldIllustration` (rising sun over agricultural furrows).
2. **Why Location Matters**:
   - Focus: Explains that rainfall varies across mountain ridges and flatlands every 5 km.
   - Visual: Custom vector `TopographyRainIllustration` (orographic ridge vs. valley microclimate).
3. **Choose Your Location**:
   - Direct integration of District → Block → Panchayat selection via `PanchayatPickerSheet`.
   - Clear summary card of the chosen village.
   - Quick option to start with pilot village (Ajmer Saundane, Baglan, Nashik).
   - "Open My Farm Dashboard" button completes onboarding.
4. **Usability Features**:
   - Language switch pill (English, मराठी, हिन्दी) pinned to top bar for immediate localization.
   - "Skip" option jumps directly to village selection.
   - Farmers can re-visit the guide anytime from the Farm Profile screen ("App Tour & Village Guide").

---

## 3. Panchayat Selection Experience
- Seamlessly uses the Phase 3.6 progressive hierarchy:
  $$\text{District} \longrightarrow \text{Block} \longrightarrow \text{Panchayat}$$
- Human-readable names across all steps (e.g., `Nashik District`, `Baglan Block`, `Ajmer Saundane GP`).
- Debounced server-side search input for fast filtering.
- Bounded pagination controls with total record counts.
- Strict minimum touch targets of 48px × 48px with clear selection highlights.
- Resilient loading, empty, and retryable error states.

---

## 4. Home Screen Redesign
Refined `HomeForecastScreen` (`farmer_app/lib/screens/home_forecast_screen.dart`):
1. **Location Bar**:
   - Displays selected Panchayat name with Block and District subtitle.
   - Compact "Change Village" chip with accessible tap target (>= 48px).
2. **Today's Micro-Forecast (`WeatherHeroCard`)**:
   - Restrained metric display: rainfall value at 30px (reduced from oversized 42px) with 14px unit.
   - Clean weather condition container (56px × 56px) with semantic icon and pastel tint.
   - Localized category badge (Light / Moderate / Heavy Rain).
3. **High-Priority Agro-Advisory (`AdvisoryCard`)**:
   - Actionable agronomist advice (e.g., spraying window, field drainage).
   - Prominent Audio Listen CTA ("Listen in Marathi / Hindi / English") with undulating `AudioWaveformIllustration` animation during playback.
   - Agromet SMS Officer verification seal with agromet unit badge.
4. **Operational Guidance Glance (`MetricTile`)**:
   - Spraying status (Safe / Postpone).
   - Rain risk level (Low / Medium / High / Critical).
5. **Secondary Information**:
   - 24-hour summary and navigation button.
   - Toll-free Kisan Call Centre banner (1800-180-1551).

---

## 5. Visual Language & Animations
- **Palette**: Strictly follows Universal Farmer Product Design System:
  - Primary Dark Forest Green (`#056B43`), Grass Green (`#087A4B`), Leaf Green (`#0A8A57`).
  - Warm Sand Canvas (`#F3F4F2`), Crisp White Surface (`#FFFFFF`).
  - Deep Earth Charcoal Ink (`#1E2823`), Muted Ink (`#77847C`).
- **Illustrations**: Zero heavy image assets. All illustrations are vector `CustomPainter` widgets:
  - `AgriSunFieldIllustration`
  - `TopographyRainIllustration`
  - `AudioWaveformIllustration`
- **Animations**: Short (< 300ms) implicit transitions for page indicators, tab shifts, and audio waveforms.

---

## 6. Accessibility & Responsive Performance
- Enforces minimum 48px touch targets for buttons, chips, and list tiles.
- Semantic labels on location selectors, audio buttons, and forecast metrics.
- Fluid layouts with zero horizontal scroll on small screens (360px width) up to tablets.
- Low-end device friendly: zero heavy third-party animation libraries, minimal memory footprint.

---

## 7. Verification & Tests
- `flutter analyze`: **0 issues found**.
- `flutter test`: **35/35 tests passed** across all test suites (`onboarding_home_test.dart`, `hierarchy_integration_test.dart`, `farmer_api_integration_test.dart`, `localization_test.dart`, `widget_test.dart`).
- React website tests: **20/20 passed** in `officer_dashboard` without regression.

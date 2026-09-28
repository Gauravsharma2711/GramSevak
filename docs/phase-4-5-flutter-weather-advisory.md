# Phase 4.5: Flutter Weather & Advisory Experience

## Executive Summary

Phase 4.5 redesigns the Flutter farmer app's Weather and Advisory experience based on the **Universal Farmer Product Design System**, **Phase 4.1 UX architecture**, and **Phase 4.4 onboarding foundation**. The redesigned interface delivers high legibility, calm agricultural aesthetics, and an intuitive **3-Tier Advisory Experience** (**What is happening? → Why it matters → What you can do**) without modifying ML models, backend APIs, or forecast calculations.

---

## 1. Weather UX & Forecast Presentation Changes

### Hierarchy & Scannability
- **Selected Panchayat Header**: Positioned prominently at the top with human-readable names (`Panchayat Name`, `Block Block, District`), clean location pin, and a dedicated `Change Village` pill action.
- **Restrained Rainfall Typography**: Standardized on a 30–32px numeric display with a 14–15px unit label (`mm`), avoiding oversized numbers.
- **Contextual Weather Alert Banner**: Dynamically rendered when `rainfallMm >= 64.5` (heavy rain) or `severity == 'HIGH' / 'CRITICAL'`. Communicates risks (e.g. soil erosion, waterlogging) without panicking the farmer.
- **Date Navigation & View Tabs**:
  - `Primary Forecast`: Focuses on tomorrow's downscaled forecast date, IMD rainfall category, and agricultural metric tiles.
  - `Time-of-Day Outlook`: Provides morning (`06:00 - 12:00`), afternoon (`12:00 - 18:00`), and evening/night (`18:00+`) field conditions with concrete operational tips.
- **Scientific Trust & Explainability**: A dedicated card clarifies that predictions are downscaled specifically to the village microclimate and verified against regional agromet models.

---

## 2. Advisory Experience: The 3-Tier Explanatory Flow

In accordance with Phase 4.1 guidelines, advisory guidance is structured into three clean, progressive steps:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. WHAT IS HAPPENING?                                       │
│    Predicted rainfall level (mm), category, and severity    │
├─────────────────────────────────────────────────────────────┤
│ 2. WHY IT MATTERS FOR YOUR FIELD                            │
│    Spraying runoff risks, root zone waterlogging, soil state│
├─────────────────────────────────────────────────────────────┤
│ 3. WHAT YOU CAN DO (RECOMMENDED ACTIONS)                    │
│    Bulleted, numbered field actions verified by officers    │
└─────────────────────────────────────────────────────────────┘
```

- **Prominent Recommendation Highlight**: The high-level action (`advisoryTitle`) is emphasized in an elevated card with a recommendation badge.
- **Officer Verification & Integrity**:
  - Approved advisories display the official extension officer seal (`Icons.verified_user` / `Icons.verified`) and District Agromet Unit attribution.
  - Unapproved or pending advisories (`isApproved == false`) display a dignified "Advisory Under Officer Review" state, never exposing draft or unapproved text.
- **Multi-Lingual Audio Read-Aloud**:
  - Farmers can tap `Listen` to hear audio in English, Marathi (`मराठी`), or Hindi (`हिन्दी`).
  - Active audio triggers a real-time `AudioWaveformIllustration` indicator.
- **Direct Helpline Access**: Includes a direct link to the Kisan Call Centre (`1800-180-1551`).

---

## 3. Visual Language & Custom Micro-Illustrations

All visuals are vector-drawn via Flutter `CustomPainter`, ensuring **zero raster image overhead** and instantaneous 60 FPS renders on budget devices:

1. **`WeatherConditionIllustration`**:
   - `Clear / Sunny`: Warm golden sun with subtle solar rays and breeze arc.
   - `Light Rain`: Soft sky-blue cloud with friendly raindrops.
   - `Moderate Rain`: Agricultural green/slate cloud with steady rain streaks.
   - `Heavy Rain / Thunderstorm`: Slate-storm cloud with amber lightning spark and dense rainfall.
2. **`RainfallGaugeIllustration`**:
   - Horizontal segmented indicator representing IMD standard thresholds (`No/Light <7.5mm`, `Moderate 7.6-64.4mm`, `Heavy ≥64.5mm`).
   - Dynamic marker dot pinpointing the exact downscaled rainfall forecast.
3. **`AudioWaveformIllustration`**:
   - 4-bar pulsating equalizer visually confirming audio playback.

---

## 4. Responsive Behavior & Accessibility

- **Device Support**: Tested across small phones (360dp), standard screens (393dp), and tablets (768dp) without horizontal scrolling or text clipping.
- **Touch Target Sizing**: All interactive buttons, chips, and village selectors satisfy `≥ 48dp` touch guidelines.
- **Color Contrast & Semantics**:
  - High-contrast text tokens (`ink900`, `ink700`, `primary700`).
  - Screen reader semantics via `Semantics` widgets for rainfall amounts, village changes, and audio controls.
  - Information is conveyed through dual encoding (color + text + icon).

---

## 5. Performance Verification

- **Asset Footprint**: Zero binary images, fonts, or external animation libraries added.
- **Tests**: **41/41** tests passing (`flutter test`), including unit, widget, and complete hierarchy integration suites.
- **Static Analysis**: `flutter analyze` completed with **0 issues found**.

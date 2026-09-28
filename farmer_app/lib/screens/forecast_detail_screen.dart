import 'package:flutter/material.dart';
import '../models/farmer_forecast.dart';
import '../theme/app_theme.dart';
import '../widgets/metric_tile.dart';
import '../widgets/agricultural_illustrations.dart';
import '../l10n/app_localizations.dart';

/// Detailed Weather Forecast Screen for Farmers
/// Free of technical ML jargon; focused on actionable field weather
class ForecastDetailScreen extends StatefulWidget {
  final FarmerForecast forecast;
  final VoidCallback onRefresh;
  final VoidCallback onSwitchPanchayat;

  const ForecastDetailScreen({
    super.key,
    required this.forecast,
    required this.onRefresh,
    required this.onSwitchPanchayat,
  });

  @override
  State<ForecastDetailScreen> createState() => _ForecastDetailScreenState();
}

class _ForecastDetailScreenState extends State<ForecastDetailScreen> {
  int _selectedViewTab = 0; // 0: Overview, 1: Time Slots

  String _getCategoryLabel(String category, AppLocalizations l10n) {
    switch (category.toUpperCase()) {
      case 'LIGHT_RAIN':
        return l10n.categoryLightRain;
      case 'MODERATE_RAIN':
        return l10n.categoryModerateRain;
      case 'HEAVY_RAIN':
      case 'VERY_HEAVY_RAIN':
        return l10n.categoryHeavyRain;
      case 'NO_RAIN':
        return l10n.categoryNoRain;
      default:
        return category.replaceAll('_', ' ');
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    final isHeavy = widget.forecast.rainfallMm >= 64.5;
    final isModerate =
        widget.forecast.rainfallMm >= 7.6 && widget.forecast.rainfallMm < 64.5;

    final categoryColor = isHeavy
        ? AppColors.danger600
        : isModerate
            ? AppColors.primary700
            : AppColors.info600;

    final badgeBg = isHeavy
        ? AppColors.danger100
        : isModerate
            ? AppColors.primary100
            : AppColors.info100;

    final categoryLabel =
        _getCategoryLabel(widget.forecast.rainfallCategory, l10n);

    return RefreshIndicator(
      onRefresh: () async => widget.onRefresh(),
      color: AppColors.primary500,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. Top Location Header Card
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE5EAE7)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.location_on,
                                size: 16, color: AppColors.primary700),
                            const SizedBox(width: 4),
                            Flexible(
                              child: Text(
                                widget.forecast.panchayatName,
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.ink900,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${widget.forecast.blockName} Block, ${widget.forecast.districtName}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.ink500,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Semantics(
                    button: true,
                    label: '${l10n.changeVillage}: ${widget.forecast.panchayatName}',
                    child: InkWell(
                      onTap: widget.onSwitchPanchayat,
                      borderRadius: BorderRadius.circular(999),
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: AppColors.primary050,
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(color: AppColors.primary100),
                        ),
                        child: Text(
                          l10n.changeVillage,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: AppColors.primary700,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),

            // 2. Weather Alert Banner (Shown during heavy rain or critical severity)
            if (isHeavy || widget.forecast.severity == 'CRITICAL' || widget.forecast.severity == 'HIGH') ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.danger100,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: const Color(0xFFF5C6CB)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.warning_amber_rounded,
                        color: AppColors.danger600, size: 22),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            l10n.alertHighRain,
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppColors.danger600,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            l10n.alertHighRainDesc,
                            style: const TextStyle(
                              fontSize: 11.5,
                              color: AppColors.ink700,
                              height: 1.4,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 14),

            // 3. Simple Forecast Date & Outlook Tab Selector
            Container(
              padding: const EdgeInsets.all(4),
              decoration: BoxDecoration(
                color: AppColors.surfaceSubtle,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.ink300),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: _buildTabButton(
                      title: '${l10n.primaryForecastDay} (${widget.forecast.forecastDate})',
                      isSelected: _selectedViewTab == 0,
                      onTap: () => setState(() => _selectedViewTab = 0),
                    ),
                  ),
                  Expanded(
                    child: _buildTabButton(
                      title: l10n.hourlyBreakdown,
                      isSelected: _selectedViewTab == 1,
                      onTap: () => setState(() => _selectedViewTab = 1),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            // 4. View Content Switcher
            if (_selectedViewTab == 0) ...[
              // Expected Rainfall Overview Card
              Container(
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isHeavy
                        ? const Color(0xFFF5C6CB)
                        : const Color(0xFFE5EAE7),
                    width: 1.5,
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '${l10n.tomorrow} • ${widget.forecast.forecastDate}',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppColors.ink500,
                          ),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: badgeBg,
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            categoryLabel,
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                              color: categoryColor,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 14),

                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              l10n.panchayatRainfall,
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: AppColors.ink500,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.baseline,
                              textBaseline: TextBaseline.alphabetic,
                              children: [
                                Text(
                                  widget.forecast.rainfallMm.toStringAsFixed(1),
                                  style: TextStyle(
                                    fontSize: 32,
                                    fontWeight: FontWeight.w800,
                                    color: categoryColor,
                                    height: 1.0,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                const Text(
                                  'mm',
                                  style: TextStyle(
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600,
                                    color: AppColors.ink700,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                        WeatherConditionIllustration(
                          rainfallMm: widget.forecast.rainfallMm,
                          size: 56,
                        ),
                      ],
                    ),

                    const SizedBox(height: 16),
                    const Divider(color: Color(0xFFF0F4F1), height: 1),
                    const SizedBox(height: 14),

                    // IMD Rainfall Scale Indicator
                    Text(
                      l10n.imdRainfallScale,
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: AppColors.ink700,
                      ),
                    ),
                    const SizedBox(height: 6),
                    RainfallGaugeIllustration(
                      rainfallMm: widget.forecast.rainfallMm,
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 18),

              // Agricultural Field Operational Guidance Grid
              Text(
                l10n.operationalGuidance,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppColors.ink900,
                ),
              ),
              const SizedBox(height: 10),

              Row(
                children: [
                  Expanded(
                    child: MetricTile(
                      label: l10n.sprayingWindow,
                      value: widget.forecast.rainfallMm > 2.5
                          ? l10n.postpone
                          : l10n.safeWindow,
                      icon: Icons.grass,
                      iconColor: widget.forecast.rainfallMm > 2.5
                          ? AppColors.warning600
                          : AppColors.primary600,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: MetricTile(
                      label: l10n.fieldTillage,
                      value: isHeavy ? l10n.delay : l10n.permitted,
                      icon: Icons.agriculture_outlined,
                      iconColor:
                          isHeavy ? AppColors.danger600 : AppColors.primary600,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: MetricTile(
                      label: l10n.fieldDrainage,
                      value: widget.forecast.rainfallMm >= 20.0
                          ? l10n.openTrenches
                          : l10n.normal,
                      icon: Icons.water_damage_outlined,
                      iconColor: widget.forecast.rainfallMm >= 20.0
                          ? AppColors.warning600
                          : AppColors.primary600,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: MetricTile(
                      label: l10n.rainRiskLevel,
                      value: widget.forecast.severity,
                      icon: Icons.shield_outlined,
                      iconColor:
                          isHeavy ? AppColors.danger600 : AppColors.primary600,
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 18),

              // Trust & Verification Note
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: const Color(0xFFE5EAE7)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline,
                        size: 16, color: AppColors.primary700),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            l10n.forecastBasis,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: AppColors.ink900,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Downscaled weather prediction for ${widget.forecast.panchayatName}, ${widget.forecast.blockName} Block. Verified against regional agromet models.',
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.ink500,
                              height: 1.4,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ] else ...[
              // Time-of-Day Weather Breakdown View
              Text(
                l10n.timeOfDayOutlook,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: AppColors.ink900,
                ),
              ),
              const SizedBox(height: 10),

              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFE5EAE7)),
                ),
                child: Column(
                  children: [
                    _buildTimeSlotRow(
                      'Morning (06:00 - 12:00)',
                      widget.forecast.rainfallMm > 15
                          ? 'Overcast / Showers'
                          : 'Partly Cloudy / Clear',
                      Icons.wb_twilight,
                      widget.forecast.rainfallMm > 15
                          ? 'Avoid chemical sprays'
                          : 'Favorable for weeding & light irrigation',
                    ),
                    const Divider(height: 22, color: Color(0xFFF0F4F1)),
                    _buildTimeSlotRow(
                      'Afternoon (12:00 - 18:00)',
                      widget.forecast.rainfallMm > 5
                          ? 'Scattered Rain'
                          : 'Moderate Sun / Warm',
                      Icons.wb_sunny_outlined,
                      widget.forecast.rainfallMm > 5
                          ? 'Monitor low-lying plots for pooling'
                          : 'Normal field work & intercultural operations',
                    ),
                    const Divider(height: 22, color: Color(0xFFF0F4F1)),
                    _buildTimeSlotRow(
                      'Evening & Night (18:00+)',
                      widget.forecast.rainfallMm > 0
                          ? 'Cool / Damp Soil'
                          : 'Dry & Clear',
                      Icons.nights_stay_outlined,
                      'Check bunds, trenches, and nursery coverings',
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildTabButton({
    required String title,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.surface : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 2,
                    offset: const Offset(0, 1),
                  ),
                ]
              : null,
        ),
        child: Text(
          title,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 11.5,
            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
            color: isSelected ? AppColors.primary700 : AppColors.ink500,
          ),
          overflow: TextOverflow.ellipsis,
        ),
      ),
    );
  }

  Widget _buildTimeSlotRow(
      String time, String condition, IconData icon, String tip) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: AppColors.primary050,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 20, color: AppColors.primary700),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                time,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: AppColors.ink900,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                condition,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppColors.primary700,
                ),
              ),
              const SizedBox(height: 1),
              Text(
                tip,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.ink500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}


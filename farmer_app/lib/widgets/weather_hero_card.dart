import 'package:flutter/material.dart';
import '../models/farmer_forecast.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';
import 'agricultural_illustrations.dart';

class WeatherHeroCard extends StatelessWidget {
  final FarmerForecast forecast;

  const WeatherHeroCard({
    super.key,
    required this.forecast,
  });

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
    final isHeavy = forecast.rainfallMm >= 64.5;
    final isModerate = forecast.rainfallMm >= 7.6 && forecast.rainfallMm < 64.5;

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

    final categoryLabel = _getCategoryLabel(forecast.rainfallCategory, l10n);

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isHeavy ? const Color(0xFFF5C6CB) : const Color(0xFFE5EAE7),
          width: 1.5,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF1E2823).withValues(alpha: 0.04),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top Header: Date & Pilot District
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.calendar_today_outlined,
                      size: 14,
                      color: AppColors.ink500,
                    ),
                    const SizedBox(width: 6),
                    Flexible(
                      child: Text(
                        '${l10n.tomorrow} • ${forecast.forecastDate}',
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppColors.ink700,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 6),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
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

          const SizedBox(height: 16),

          // Main Display: Rainfall Metric & Weather Condition Illustration
          Semantics(
            label: '${l10n.panchayatRainfall}: ${forecast.rainfallMm.toStringAsFixed(1)} millimeters, $categoryLabel',
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      l10n.panchayatRainfall,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: AppColors.ink500,
                        letterSpacing: 0.3,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          forecast.rainfallMm.toStringAsFixed(1),
                          style: TextStyle(
                            fontSize: 30,
                            fontWeight: FontWeight.w800,
                            color: categoryColor,
                            height: 1.1,
                            letterSpacing: -0.5,
                          ),
                        ),
                        const SizedBox(width: 4),
                        const Text(
                          'mm',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                            color: AppColors.ink700,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              // Weather Condition Illustration
                WeatherConditionIllustration(
                  rainfallMm: forecast.rainfallMm,
                  size: 56,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}


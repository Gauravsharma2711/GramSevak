import 'package:flutter/material.dart';
import '../models/farmer_forecast.dart';
import '../widgets/weather_hero_card.dart';
import '../widgets/advisory_card.dart';
import '../widgets/metric_tile.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';

class HomeForecastScreen extends StatefulWidget {
  final FarmerForecast forecast;
  final VoidCallback onRefresh;
  final VoidCallback onSwitchPanchayat;
  final VoidCallback? onViewForecastDetails;
  final VoidCallback? onViewAdvisoryDetails;

  const HomeForecastScreen({
    super.key,
    required this.forecast,
    required this.onRefresh,
    required this.onSwitchPanchayat,
    this.onViewForecastDetails,
    this.onViewAdvisoryDetails,
  });

  @override
  State<HomeForecastScreen> createState() => _HomeForecastScreenState();
}

class _HomeForecastScreenState extends State<HomeForecastScreen> {
  bool _isPlayingAudio = false;

  void _handleAudioPlay() {
    setState(() => _isPlayingAudio = true);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Playing verified audio advisory for ${widget.forecast.panchayatName}...',
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        backgroundColor: AppColors.primary700,
        duration: const Duration(seconds: 3),
        behavior: SnackBarBehavior.floating,
      ),
    );
    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) setState(() => _isPlayingAudio = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return RefreshIndicator(
      onRefresh: () async => widget.onRefresh(),
      color: AppColors.primary500,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top Welcome Greeting & Location Pill
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.forecast.panchayatName,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w800,
                          color: AppColors.ink900,
                          letterSpacing: -0.3,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                      Text(
                        '${widget.forecast.blockName} Block, ${widget.forecast.districtName}',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.ink500,
                          fontWeight: FontWeight.w500,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Semantics(
                  button: true,
                  label: '${l10n.changeVillage}: currently ${widget.forecast.panchayatName}',
                  child: InkWell(
                    onTap: widget.onSwitchPanchayat,
                    borderRadius: BorderRadius.circular(999),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: AppColors.ink300),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.swap_horiz, size: 16, color: AppColors.primary700),
                          const SizedBox(width: 4),
                          Text(
                            l10n.changeVillage,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: AppColors.primary700,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),

            const SizedBox(height: 16),

            // Section 1: Today's / Next Forecast Label
            Row(
              children: [
                const Icon(Icons.cloud_outlined, size: 16, color: AppColors.primary700),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    l10n.todaysForecast,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w700,
                      color: AppColors.ink900,
                      letterSpacing: 0.2,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 8),

            // Hero Weather Card (Downscaled Rainfall)
            WeatherHeroCard(forecast: widget.forecast),

            const SizedBox(height: 16),

            // Key Agricultural Metric Tiles Row
            Row(
              children: [
                Expanded(
                  child: MetricTile(
                    label: l10n.sprayingWindow,
                    value: widget.forecast.rainfallMm > 2.5 ? l10n.postpone : l10n.safeWindow,
                    icon: Icons.grass,
                    iconColor: widget.forecast.rainfallMm > 2.5
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
                    iconColor: widget.forecast.severity == 'HIGH'
                        ? AppColors.danger600
                        : AppColors.primary600,
                  ),
                ),
              ],
            ),

            const SizedBox(height: 20),

            // Section 2: Agricultural Advisory
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Row(
                    children: [
                      const Icon(Icons.assignment_turned_in_outlined, size: 16, color: AppColors.primary700),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          l10n.agriculturalAdvisory,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                            color: AppColors.ink900,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                ),
                if (widget.onViewAdvisoryDetails != null) ...[
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: widget.onViewAdvisoryDetails,
                    child: Text(
                      l10n.viewAllAdvice,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: AppColors.primary700,
                      ),
                    ),
                  ),
                ],
              ],
            ),

            const SizedBox(height: 10),

            // Officer Verified Advisory Card
            AdvisoryCard(
              forecast: widget.forecast,
              onAudioPlay: _handleAudioPlay,
              isPlayingAudio: _isPlayingAudio,
            ),

            const SizedBox(height: 16),

            // Section 3: Forecast Details & Operational Summary
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE5EAE7)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(
                        child: Text(
                          l10n.forecastDetails,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: AppColors.ink900,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Icon(Icons.wb_sunny_outlined, size: 16, color: AppColors.primary700),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${l10n.panchayatRainfall}: ${widget.forecast.rainfallMm.toStringAsFixed(1)} mm (${widget.forecast.rainfallCategory.replaceAll('_', ' ')}).',
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.ink700,
                      height: 1.4,
                    ),
                  ),
                  if (widget.onViewForecastDetails != null) ...[
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: widget.onViewForecastDetails,
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 38),
                        side: const BorderSide(color: AppColors.primary500),
                      ),
                      child: Text(
                        l10n.view24HourBreakdown,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: AppColors.primary700,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),

            const SizedBox(height: 20),

            // Bottom Helpline Action Banner
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.primary050,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.primary100),
              ),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: AppColors.primary500,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(
                      Icons.support_agent,
                      color: AppColors.surface,
                      size: 22,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          l10n.kisanCallCentre,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: AppColors.ink900,
                          ),
                        ),
                        Text(
                          l10n.kisanCallCentreSub,
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.ink700,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

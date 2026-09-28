import 'package:flutter/material.dart';
import '../models/farmer_forecast.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';
import 'agricultural_illustrations.dart';

class AdvisoryCard extends StatelessWidget {
  final FarmerForecast forecast;
  final VoidCallback onAudioPlay;
  final bool isPlayingAudio;

  const AdvisoryCard({
    super.key,
    required this.forecast,
    required this.onAudioPlay,
    this.isPlayingAudio = false,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    if (!forecast.isApproved) {
      return Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFE5EAE7)),
        ),
        child: Column(
          children: [
            const Icon(
              Icons.hourglass_empty,
              color: AppColors.warning600,
              size: 28,
            ),
            const SizedBox(height: 8),
            Text(
              l10n.advisoryUnderReview,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: AppColors.ink900,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              l10n.advisoryUnderReviewDesc,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 12,
                color: AppColors.ink500,
                height: 1.4,
              ),
            ),
          ],
        ),
      );
    }

    final isHighSeverity = forecast.severity == 'HIGH' || forecast.severity == 'CRITICAL';
    final isMediumSeverity = forecast.severity == 'MEDIUM';

    final borderColor = isHighSeverity
        ? const Color(0xFFF5C6CB)
        : isMediumSeverity
            ? const Color(0xFFFFEEBA)
            : const Color(0xFFD4EDDA);

    final bannerBg = isHighSeverity
        ? AppColors.danger100
        : isMediumSeverity
            ? AppColors.warning100
            : AppColors.primary050;

    final bannerTextColor = isHighSeverity
        ? AppColors.danger600
        : isMediumSeverity
            ? AppColors.warning600
            : AppColors.primary700;

    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: borderColor, width: 1.5),
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
          // Officer Approval Verification Banner
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: bannerBg,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(18),
              ),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(
                      Icons.verified_user,
                      size: 18,
                      color: bannerTextColor,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      l10n.officerVerifiedAdvisory,
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                        color: bannerTextColor,
                      ),
                    ),
                  ],
                ),

                // Audio Read-Aloud / Voice Button for Farmers
                Semantics(
                  button: true,
                  label: isPlayingAudio ? l10n.listeningAudio : l10n.listenAudio,
                  child: InkWell(
                    onTap: onAudioPlay,
                    borderRadius: BorderRadius.circular(999),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: AppColors.ink300),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (isPlayingAudio) ...[
                            const AudioWaveformIllustration(isPlaying: true),
                            const SizedBox(width: 6),
                          ] else ...[
                            const Icon(
                              Icons.volume_up_outlined,
                              size: 16,
                              color: AppColors.primary700,
                            ),
                            const SizedBox(width: 6),
                          ],
                          Text(
                            isPlayingAudio ? l10n.listeningAudio : l10n.listenAudio,
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
          ),

          // Advisory Title and Content
          Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (forecast.advisoryTitle != null) ...[
                  Text(
                    forecast.advisoryTitle!,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                      color: AppColors.ink900,
                      height: 1.3,
                    ),
                  ),
                  const SizedBox(height: 14),
                ],

                // Actionable Advisory Points
                ...forecast.advisoryPoints.map(
                  (point) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          margin: const EdgeInsets.only(top: 5, right: 10),
                          width: 6,
                          height: 6,
                          decoration: const BoxDecoration(
                            color: AppColors.primary600,
                            shape: BoxShape.circle,
                          ),
                        ),
                        Expanded(
                          child: Text(
                            point,
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.ink700,
                              height: 1.45,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

                const SizedBox(height: 8),
                const Divider(color: Color(0xFFF0F4F1), height: 1),
                const SizedBox(height: 10),

                // Footer Note
                Row(
                  children: [
                    const Icon(
                      Icons.shield_outlined,
                      size: 14,
                      color: AppColors.ink500,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        l10n.verifiedByOfficer,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppColors.ink500,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

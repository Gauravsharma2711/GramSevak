import 'package:flutter/material.dart';
import '../models/farmer_forecast.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';
import '../widgets/agricultural_illustrations.dart';

/// Detailed Advisory Screen for Farmers
/// Implements the 3-Tier Agro-Advisory UX Structure:
/// 1. WHAT IS HAPPENING?
/// 2. WHY IT MATTERS
/// 3. WHAT YOU CAN DO
class AdvisoryDetailScreen extends StatefulWidget {
  final FarmerForecast forecast;
  final VoidCallback onRefresh;
  final String currentLang;
  final Function(String) onLanguageChanged;

  const AdvisoryDetailScreen({
    super.key,
    required this.forecast,
    required this.onRefresh,
    required this.currentLang,
    required this.onLanguageChanged,
  });

  @override
  State<AdvisoryDetailScreen> createState() => _AdvisoryDetailScreenState();
}

class _AdvisoryDetailScreenState extends State<AdvisoryDetailScreen> {
  bool _isPlayingAudio = false;

  void _handleAudioPlay() {
    if (!widget.forecast.isApproved) return;
    setState(() => _isPlayingAudio = true);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          'Playing verified voice advisory in ${widget.currentLang == 'mr' ? 'Marathi (मराठी)' : widget.currentLang == 'hi' ? 'Hindi (हिन्दी)' : 'English'}...',
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
    final isApproved = widget.forecast.isApproved;

    return RefreshIndicator(
      onRefresh: () async => widget.onRefresh(),
      color: AppColors.primary500,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top Language Switcher Bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE5EAE7)),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.translate,
                          size: 16, color: AppColors.primary700),
                      const SizedBox(width: 6),
                      Text(
                        l10n.preferredLanguage,
                        style: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: AppColors.ink700,
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      _buildLangChip('en', 'EN'),
                      const SizedBox(width: 6),
                      _buildLangChip('mr', 'मराठी'),
                      const SizedBox(width: 6),
                      _buildLangChip('hi', 'हिंदी'),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 14),

            if (isApproved) ...[
              // 1. Officer Verified Status Header Banner
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
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: AppColors.primary100,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.verified,
                        color: AppColors.primary700,
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Flexible(
                                child: Text(
                                  l10n.officerVerifiedAdvisory,
                                  style: const TextStyle(
                                    fontSize: 14,
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.primary700,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppColors.surface,
                                  borderRadius: BorderRadius.circular(999),
                                  border:
                                      Border.all(color: AppColors.primary100),
                                ),
                                child: Text(
                                  widget.forecast.severity,
                                  style: const TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.primary700,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            '${widget.forecast.panchayatName} (${widget.forecast.blockName}) • ${widget.forecast.forecastDate}',
                            style: const TextStyle(
                              fontSize: 11.5,
                              color: AppColors.ink700,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 14),

              // 2. Audio Read-Aloud Voice Card
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
                          Text(
                            l10n.audioAdvisory,
                            style: const TextStyle(
                              fontSize: 13.5,
                              fontWeight: FontWeight.w700,
                              color: AppColors.ink900,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            l10n.tapToListen,
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppColors.ink500,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    ElevatedButton.icon(
                      onPressed: _handleAudioPlay,
                      icon: _isPlayingAudio
                          ? const AudioWaveformIllustration(
                              isPlaying: true, color: AppColors.surface)
                          : const Icon(Icons.volume_up_outlined, size: 16),
                      label: Text(
                        _isPlayingAudio
                            ? l10n.listeningAudio
                            : l10n.listenAudio,
                      ),
                      style: ElevatedButton.styleFrom(
                        minimumSize: const Size(110, 40),
                        backgroundColor: AppColors.primary500,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // 3. Main Recommendation Highlight Card
              if (widget.forecast.advisoryTitle != null) ...[
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: AppColors.primary100, width: 1.5),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(Icons.star_outline,
                              size: 16, color: AppColors.primary700),
                          const SizedBox(width: 6),
                          Text(
                            l10n.recommendedAction,
                            style: const TextStyle(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w700,
                              color: AppColors.primary700,
                              letterSpacing: 0.2,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        widget.forecast.advisoryTitle!,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: AppColors.ink900,
                          height: 1.35,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],

              // 4. THE 3-TIER ADVISORY FLOW CONTAINER
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFFE5EAE7)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // TIER 1: WHAT IS HAPPENING?
                    _buildSectionHeader(
                      number: '1',
                      title: l10n.whatIsHappening,
                      icon: Icons.cloud_outlined,
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceSubtle,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.water_drop_outlined,
                              size: 18, color: AppColors.primary700),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              widget.forecast.whatIsHappening ??
                                  '${widget.forecast.rainfallMm.toStringAsFixed(1)} mm rainfall (${widget.forecast.rainfallCategory.replaceAll('_', ' ')}) predicted for ${widget.forecast.panchayatName}.',
                              style: const TextStyle(
                                fontSize: 13,
                                color: AppColors.ink900,
                                fontWeight: FontWeight.w600,
                                height: 1.4,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 18),
                    const Divider(color: Color(0xFFF0F4F1), height: 1),
                    const SizedBox(height: 18),

                    // TIER 2: WHY IT MATTERS
                    _buildSectionHeader(
                      number: '2',
                      title: l10n.whyItMatters,
                      icon: Icons.psychology_outlined,
                    ),
                    const SizedBox(height: 8),
                    if (widget.forecast.whyItMatters != null) ...[
                      Container(
                        padding: const EdgeInsets.all(12),
                        margin: const EdgeInsets.only(bottom: 10),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceSubtle,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          widget.forecast.whyItMatters!,
                          style: const TextStyle(
                            fontSize: 13,
                            color: AppColors.ink900,
                            fontWeight: FontWeight.w500,
                            height: 1.4,
                          ),
                        ),
                      ),
                    ],
                    _buildReasonRow(
                      icon: Icons.grass,
                      title: l10n.sprayingWindow,
                      explanation: widget.forecast.rainfallMm > 2.5
                          ? 'Sprayed pesticides or fertilizers risk runoff wash-off.'
                          : 'Dry foliage ensures maximum chemical absorption.',
                    ),
                    const SizedBox(height: 8),
                    _buildReasonRow(
                      icon: Icons.water_damage_outlined,
                      title: l10n.fieldDrainage,
                      explanation: widget.forecast.rainfallMm >= 20.0
                          ? 'Risk of standing water and root rot in clay soils.'
                          : 'Normal moisture balance expected for crops.',
                    ),

                    const SizedBox(height: 18),
                    const Divider(color: Color(0xFFF0F4F1), height: 1),
                    const SizedBox(height: 18),

                    // TIER 3: WHAT YOU CAN DO (RECOMMENDED ACTIONS)
                    _buildSectionHeader(
                      number: '3',
                      title: l10n.whatYouCanDo,
                      icon: Icons.checklist_outlined,
                    ),
                    const SizedBox(height: 12),

                    ...(widget.forecast.recommendedActions.isNotEmpty
                            ? widget.forecast.recommendedActions
                            : widget.forecast.advisoryPoints)
                        .asMap()
                        .entries
                        .map(
                      (entry) {
                        final idx = entry.key + 1;
                        final point = entry.value;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Container(
                                width: 22,
                                height: 22,
                                margin:
                                    const EdgeInsets.only(top: 2, right: 10),
                                decoration: const BoxDecoration(
                                  color: AppColors.primary050,
                                  shape: BoxShape.circle,
                                ),
                                child: Center(
                                  child: Text(
                                    '$idx',
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w700,
                                      color: AppColors.primary700,
                                    ),
                                  ),
                                ),
                              ),
                              Expanded(
                                child: Text(
                                  point,
                                  style: const TextStyle(
                                    fontSize: 13.5,
                                    color: AppColors.ink900,
                                    height: 1.5,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),

                    if (widget.forecast.timing != null) ...[
                      const SizedBox(height: 10),
                      const Divider(color: Color(0xFFF0F4F1), height: 1),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          const Icon(Icons.schedule,
                              size: 16, color: AppColors.primary700),
                          const SizedBox(width: 8),
                          Text(
                            l10n.timingOutlook,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              color: AppColors.primary700,
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              widget.forecast.timing!,
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.ink700,
                                fontWeight: FontWeight.w600,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],

                    if (widget.forecast.warnings.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      const Divider(color: Color(0xFFF0F4F1), height: 1),
                      const SizedBox(height: 14),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppColors.warning100,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFFFFEEBA)),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                const Icon(Icons.warning_amber_rounded,
                                    size: 16, color: AppColors.warning600),
                                const SizedBox(width: 6),
                                Text(
                                  l10n.warningsTitle,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: AppColors.warning600,
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            ...widget.forecast.warnings.map(
                              (w) => Padding(
                                padding: const EdgeInsets.only(bottom: 4),
                                child: Text(
                                  '• $w',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Color(0xFF856404),
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],

                    const SizedBox(height: 14),
                    const Divider(color: Color(0xFFF0F4F1), height: 1),
                    const SizedBox(height: 12),

                    // Official Extension Verification Footer with Version
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Row(
                            children: [
                              const Icon(Icons.verified_user,
                                  size: 14, color: AppColors.primary700),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  l10n.verifiedByOfficer,
                                  style: const TextStyle(
                                    fontSize: 11,
                                    color: AppColors.ink500,
                                    fontWeight: FontWeight.w500,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (widget.forecast.advisoryVersion != null)
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: AppColors.primary050,
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              'v${widget.forecast.advisoryVersion}',
                              style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: AppColors.primary700,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ],
                ),
              ),
            ] else ...[
              // Unapproved / Pending Review State (Never display DRAFT or unapproved content)
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFFE5EAE7)),
                ),
                child: Column(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: const BoxDecoration(
                        color: AppColors.warning100,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.hourglass_empty,
                        color: AppColors.warning600,
                        size: 24,
                      ),
                    ),
                    const SizedBox(height: 12),
                    const CropSproutIllustration(size: 80),
                    const SizedBox(height: 16),
                    Text(
                      l10n.advisoryUnderReview,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.ink900,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      l10n.advisoryUnderReviewDesc,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.ink500,
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 20),
                    OutlinedButton.icon(
                      onPressed: widget.onRefresh,
                      icon: const Icon(Icons.refresh, size: 16),
                      label: Text(l10n.tryAgain),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: AppColors.primary500),
                      ),
                    ),
                  ],
                ),
              ),
            ],

            const SizedBox(height: 18),

            // Kisan Toll-Free Contact Banner
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFE5EAE7)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      color: AppColors.primary050,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.call,
                      color: AppColors.primary700,
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
                            color: AppColors.primary700,
                            fontWeight: FontWeight.w600,
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

  Widget _buildSectionHeader({
    required String number,
    required String title,
    required IconData icon,
  }) {
    return Row(
      children: [
        Container(
          width: 20,
          height: 20,
          decoration: BoxDecoration(
            color: AppColors.primary700,
            borderRadius: BorderRadius.circular(6),
          ),
          child: Center(
            child: Text(
              number,
              style: const TextStyle(
                color: AppColors.surface,
                fontSize: 11,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        Icon(icon, size: 16, color: AppColors.primary700),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            title,
            style: const TextStyle(
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
              color: AppColors.ink900,
              letterSpacing: 0.1,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildReasonRow({
    required IconData icon,
    required String title,
    required String explanation,
  }) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: AppColors.ink500),
        const SizedBox(width: 8),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: AppColors.ink900,
                ),
              ),
              Text(
                explanation,
                style: const TextStyle(
                  fontSize: 11.5,
                  color: AppColors.ink500,
                  height: 1.35,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildLangChip(String langCode, String label) {
    final isSelected = widget.currentLang == langCode;
    return GestureDetector(
      onTap: () => widget.onLanguageChanged(langCode),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary500 : AppColors.surfaceSubtle,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: isSelected ? AppColors.primary500 : AppColors.ink300,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            color: isSelected ? AppColors.surface : AppColors.ink700,
          ),
        ),
      ),
    );
  }
}


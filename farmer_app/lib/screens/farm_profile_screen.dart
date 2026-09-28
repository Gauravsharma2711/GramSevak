import 'package:flutter/material.dart';
import '../models/farmer_forecast.dart';
import '../models/panchayat_item.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';

class FarmProfileScreen extends StatelessWidget {
  final FarmerForecast forecast;
  final PanchayatItem? currentPanchayat;
  final VoidCallback onChangePanchayat;
  final String currentLang;
  final Function(String) onLanguageChanged;
  final VoidCallback? onOpenOnboarding;

  const FarmProfileScreen({
    super.key,
    required this.forecast,
    this.currentPanchayat,
    required this.onChangePanchayat,
    required this.currentLang,
    required this.onLanguageChanged,
    this.onOpenOnboarding,
  });

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Profile Header Card
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFFE5EAE7)),
            ),
            child: Row(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: AppColors.primary050,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: AppColors.primary100),
                  ),
                  child: const Icon(
                    Icons.agriculture,
                    color: AppColors.primary700,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l10n.kisanAccount,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppColors.ink900,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${forecast.panchayatName} • ${forecast.blockName} Block',
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.ink500,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Location Details Card
          Text(
            l10n.registeredVillage,
            style: const TextStyle(
              fontSize: 14,
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
                _buildInfoRow('Village Panchayat', forecast.panchayatName),
                const Divider(height: 16, color: Color(0xFFF0F4F1)),
                _buildInfoRow('Block / Tehsil', forecast.blockName),
                const Divider(height: 16, color: Color(0xFFF0F4F1)),
                _buildInfoRow('District', forecast.districtName),
                const Divider(height: 16, color: Color(0xFFF0F4F1)),
                _buildInfoRow('Terrain Elevation', currentPanchayat != null ? '${currentPanchayat!.elevationM.toInt()} m' : '540 m'),
                const SizedBox(height: 14),
                ElevatedButton.icon(
                  onPressed: onChangePanchayat,
                  icon: const Icon(Icons.location_searching, size: 16),
                  label: Text(l10n.changeVillage),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Preferred Language Selector
          Text(
            l10n.preferredLanguage,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w700,
              color: AppColors.ink900,
            ),
          ),
          const SizedBox(height: 10),

          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFE5EAE7)),
            ),
            child: Column(
              children: [
                _buildLanguageOption('en', 'English (Default)', 'Primary language interface'),
                const Divider(height: 12, color: Color(0xFFF0F4F1)),
                _buildLanguageOption('mr', 'मराठी (Marathi)', 'स्थानिक प्रादेशिक भाषा'),
                const Divider(height: 12, color: Color(0xFFF0F4F1)),
                _buildLanguageOption('hi', 'हिन्दी (Hindi)', 'राष्ट्रीय मानक भाषा'),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Helpline Card
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.primary050,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.primary100),
            ),
            child: Row(
              children: [
                const Icon(Icons.phone_in_talk, color: AppColors.primary700, size: 24),
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

          if (onOpenOnboarding != null) ...[
            const SizedBox(height: 20),
            InkWell(
              onTap: onOpenOnboarding,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: const Color(0xFFE5EAE7)),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.primary050,
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Icon(
                        Icons.explore_outlined,
                        color: AppColors.primary700,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'App Tour & Village Guide',
                            style: TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w700,
                              color: AppColors.ink900,
                            ),
                          ),
                          Text(
                            'Learn how localized micro-climate forecasts work',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppColors.ink500,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.chevron_right, size: 20, color: AppColors.ink500),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 13, color: AppColors.ink500),
        ),
        Text(
          value,
          style: const TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: AppColors.ink900,
          ),
        ),
      ],
    );
  }

  Widget _buildLanguageOption(String langCode, String title, String subtitle) {
    final isSelected = currentLang == langCode;
    return InkWell(
      onTap: () => onLanguageChanged(langCode),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary050 : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          children: [
            Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: isSelected ? AppColors.primary500 : AppColors.ink300,
                  width: 2,
                ),
              ),
              child: isSelected
                  ? Center(
                      child: Container(
                        width: 10,
                        height: 10,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppColors.primary500,
                        ),
                      ),
                    )
                  : null,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                      color: isSelected ? AppColors.primary700 : AppColors.ink900,
                    ),
                  ),
                  Text(
                    subtitle,
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.ink500,
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

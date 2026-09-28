import 'package:flutter/material.dart';
import '../models/panchayat_item.dart';
import '../repositories/farmer_repository.dart';
import '../theme/app_theme.dart';
import '../l10n/app_localizations.dart';
import '../widgets/agricultural_illustrations.dart';
import '../widgets/panchayat_picker_sheet.dart';

/// First-time Onboarding Experience for GramSevak Farmer App.
///
/// Principles (Universal Farmer Product Design System & Phase 4.1 UX):
/// - Short, simple visual story: Welcome → Why Location Matters → Choose Panchayat
/// - Accessible touch targets >= 48px
/// - Clear, restrained typography
/// - Instant language switcher (EN / मराठी / हिन्दी)
/// - Integrated Phase 3.6 District → Block → Panchayat picker
class FarmerOnboardingScreen extends StatefulWidget {
  final List<PanchayatItem> panchayats;
  final int initialPanchayatId;
  final String currentLang;
  final Function(String) onLanguageChanged;
  final Function(PanchayatItem) onCompleteOnboarding;

  const FarmerOnboardingScreen({
    super.key,
    required this.panchayats,
    required this.initialPanchayatId,
    required this.currentLang,
    required this.onLanguageChanged,
    required this.onCompleteOnboarding,
  });

  @override
  State<FarmerOnboardingScreen> createState() => _FarmerOnboardingScreenState();
}

class _FarmerOnboardingScreenState extends State<FarmerOnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;
  PanchayatItem? _selectedPanchayat;

  @override
  void initState() {
    super.initState();
    // Default to the initial/pilot Panchayat if available
    _selectedPanchayat = widget.panchayats.firstWhere(
      (p) => p.panchayatId == widget.initialPanchayatId,
      orElse: () => widget.panchayats.isNotEmpty
          ? widget.panchayats.first
          : FarmerRepository.fallbackPanchayats.first,
    );
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _openPanchayatPicker() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => PanchayatPickerSheet(
        panchayats: widget.panchayats.isNotEmpty
            ? widget.panchayats
            : FarmerRepository.fallbackPanchayats,
        selectedPanchayatId: _selectedPanchayat?.panchayatId,
        onSelect: (panchayat) {
          setState(() {
            _selectedPanchayat = panchayat;
          });
        },
      ),
    );
  }

  void _finish() {
    final chosen = _selectedPanchayat ??
        (widget.panchayats.isNotEmpty
            ? widget.panchayats.first
            : FarmerRepository.fallbackPanchayats.first);
    widget.onCompleteOnboarding(chosen);
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);

    return Scaffold(
      backgroundColor: AppColors.canvas,
      body: SafeArea(
        child: Column(
          children: [
            // Top Bar: Branding + Language Selector + Skip
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  // Logo & App Name
                  Row(
                    children: [
                      Container(
                        width: 32,
                        height: 32,
                        decoration: BoxDecoration(
                          color: AppColors.primary050,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppColors.primary100),
                        ),
                        child: const Icon(
                          Icons.eco,
                          color: AppColors.primary700,
                          size: 18,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        l10n.appName,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: AppColors.primary700,
                          letterSpacing: -0.2,
                        ),
                      ),
                    ],
                  ),

                  // Actions: Language Toggle & Optional Skip
                  Row(
                    children: [
                      _buildLangPill(),
                      if (_currentPage < 2) ...[
                        const SizedBox(width: 8),
                        TextButton(
                          onPressed: () {
                            _pageController.animateToPage(
                              2,
                              duration: const Duration(milliseconds: 300),
                              curve: Curves.easeOut,
                            );
                          },
                          style: TextButton.styleFrom(
                            foregroundColor: AppColors.ink500,
                            padding: const EdgeInsets.symmetric(horizontal: 10),
                            minimumSize: const Size(40, 36),
                          ),
                          child: Text(
                            l10n.btnSkip,
                            style: const TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),

            // Step Pages Carousel
            Expanded(
              child: PageView(
                controller: _pageController,
                onPageChanged: (idx) => setState(() => _currentPage = idx),
                children: [
                  _buildWelcomePage(l10n),
                  _buildWhyLocationPage(l10n),
                  _buildSelectionPage(l10n),
                ],
              ),
            ),

            // Bottom Navigation Footer: Indicators + CTA
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 10, 20, 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Dot Indicators
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(3, (index) {
                      final isActive = index == _currentPage;
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        width: isActive ? 24 : 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: isActive
                              ? AppColors.primary600
                              : AppColors.ink300,
                          borderRadius: BorderRadius.circular(4),
                        ),
                      );
                    }),
                  ),

                  const SizedBox(height: 18),

                  // Action Button
                  if (_currentPage < 2)
                    ElevatedButton(
                      onPressed: () {
                        _pageController.nextPage(
                          duration: const Duration(milliseconds: 250),
                          curve: Curves.easeOut,
                        );
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary500,
                        minimumSize: const Size(double.infinity, 48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
                      child: Text(
                        l10n.btnNext,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppColors.surface,
                        ),
                      ),
                    )
                  else
                    ElevatedButton(
                      onPressed: _finish,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary700,
                        minimumSize: const Size(double.infinity, 48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
                      child: Text(
                        l10n.btnGetStarted,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppColors.surface,
                        ),
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

  // --- Step 1: Welcome Page ---
  Widget _buildWelcomePage(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const AgriSunFieldIllustration(size: 160),
          const SizedBox(height: 28),
          Text(
            l10n.onboardingWelcomeTitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.ink900,
              letterSpacing: -0.3,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            l10n.onboardingWelcomeSub,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.ink700,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  // --- Step 2: Why Location Matters Page ---
  Widget _buildWhyLocationPage(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const TopographyRainIllustration(size: 160),
          const SizedBox(height: 28),
          Text(
            l10n.onboardingLocationTitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.ink900,
              letterSpacing: -0.3,
              height: 1.25,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            l10n.onboardingLocationSub,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.ink700,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  // --- Step 3: Location Selection Page ---
  Widget _buildSelectionPage(AppLocalizations l10n) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(
              color: AppColors.primary050,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: AppColors.primary100),
            ),
            child: const Icon(
              Icons.location_on_outlined,
              size: 32,
              color: AppColors.primary700,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            l10n.onboardingSelectionTitle,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.ink900,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            l10n.onboardingSelectionSub,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.ink700,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 24),

          // Selected Panchayat Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: AppColors.primary500, width: 1.5),
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
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.primary050,
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: AppColors.primary100),
                      ),
                      child: Text(
                        l10n.registeredVillage,
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          color: AppColors.primary700,
                        ),
                      ),
                    ),
                    const Icon(
                      Icons.check_circle,
                      size: 18,
                      color: AppColors.primary600,
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  _selectedPanchayat?.panchayatName ?? 'Ajmer Saundane',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: AppColors.ink900,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${_selectedPanchayat?.blockName ?? 'Baglan'} Block • ${_selectedPanchayat?.districtName ?? 'Nashik'}',
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.ink500,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // Change / Pick Location Button (opens Phase 3.6 Hierarchy Picker)
          OutlinedButton.icon(
            onPressed: _openPanchayatPicker,
            icon: const Icon(Icons.search, size: 18, color: AppColors.primary700),
            label: Text(
              l10n.btnChooseVillage,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: AppColors.primary700,
              ),
            ),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(double.infinity, 48),
              side: const BorderSide(color: AppColors.ink300),
              backgroundColor: AppColors.surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // --- Compact Language Pill ---
  Widget _buildLangPill() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.ink300),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildLangItem('EN', 'en'),
          _buildLangItem('मराठी', 'mr'),
          _buildLangItem('हिन्दी', 'hi'),
        ],
      ),
    );
  }

  Widget _buildLangItem(String label, String code) {
    final isSelected = widget.currentLang == code;
    return InkWell(
      onTap: () => widget.onLanguageChanged(code),
      borderRadius: BorderRadius.circular(999),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary500 : Colors.transparent,
          borderRadius: BorderRadius.circular(999),
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

import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Clean Empty State for Farmer Mobile App
class FarmerEmptyState extends StatelessWidget {
  final String title;
  final String description;
  final String? actionText;
  final VoidCallback? onAction;
  final IconData icon;
  final Widget? illustration;

  const FarmerEmptyState({
    super.key,
    required this.title,
    required this.description,
    this.actionText,
    this.onAction,
    this.icon = Icons.cloud_off_outlined,
    this.illustration,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            if (illustration != null)
              illustration!
            else
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: AppColors.primary050,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.primary100),
                ),
                child: Icon(
                  icon,
                  color: AppColors.primary700,
                  size: 32,
                ),
              ),
            const SizedBox(height: 16),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.ink900,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              description,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 13,
                color: AppColors.ink500,
                height: 1.4,
              ),
            ),
            if (actionText != null && onAction != null) ...[
              const SizedBox(height: 20),
              ElevatedButton.icon(
                onPressed: onAction,
                icon: const Icon(Icons.refresh, size: 16),
                label: Text(actionText!),
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(200, 44),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

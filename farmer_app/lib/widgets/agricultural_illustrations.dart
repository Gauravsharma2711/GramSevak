import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Lightweight, vector-drawn agricultural and weather illustrations using CustomPainter.
/// Zero external image assets or heavy dependencies — 60 FPS on low-end devices.

/// Stylized rising sun over green furrowed agricultural fields.
class AgriSunFieldIllustration extends StatelessWidget {
  final double size;

  const AgriSunFieldIllustration({
    super.key,
    this.size = 140,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _AgriSunFieldPainter(),
      ),
    );
  }
}

class _AgriSunFieldPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Background circle container
    final bgPaint = Paint()
      ..color = AppColors.primary050
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(w / 2, h / 2), w * 0.48, bgPaint);

    final borderPaint = Paint()
      ..color = AppColors.primary100
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawCircle(Offset(w / 2, h / 2), w * 0.48, borderPaint);

    // Warm Sun
    final sunCenter = Offset(w * 0.5, h * 0.38);
    final sunRadius = w * 0.16;

    final sunGlowPaint = Paint()
      ..color = AppColors.sun100
      ..style = PaintingStyle.fill;
    canvas.drawCircle(sunCenter, sunRadius * 1.4, sunGlowPaint);

    final sunPaint = Paint()
      ..color = AppColors.sun500
      ..style = PaintingStyle.fill;
    canvas.drawCircle(sunCenter, sunRadius, sunPaint);

    // Rolling Agricultural Field Furrows
    final fieldPaint1 = Paint()
      ..color = AppColors.primary600
      ..style = PaintingStyle.fill;

    final path1 = Path()
      ..moveTo(w * 0.08, h * 0.65)
      ..quadraticBezierTo(w * 0.35, h * 0.52, w * 0.65, h * 0.60)
      ..quadraticBezierTo(w * 0.85, h * 0.65, w * 0.92, h * 0.72)
      ..lineTo(w * 0.92, h * 0.90)
      ..lineTo(w * 0.08, h * 0.90)
      ..close();
    canvas.drawPath(path1, fieldPaint1);

    final fieldPaint2 = Paint()
      ..color = AppColors.primary700
      ..style = PaintingStyle.fill;

    final path2 = Path()
      ..moveTo(w * 0.08, h * 0.76)
      ..quadraticBezierTo(w * 0.45, h * 0.66, w * 0.92, h * 0.78)
      ..lineTo(w * 0.92, h * 0.92)
      ..lineTo(w * 0.08, h * 0.92)
      ..close();
    canvas.drawPath(path2, fieldPaint2);

    // Furrow lines
    final furrowPaint = Paint()
      ..color = const Color(0xFFDDF3E8).withValues(alpha: 0.35)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;

    canvas.drawLine(Offset(w * 0.25, h * 0.72), Offset(w * 0.35, h * 0.86), furrowPaint);
    canvas.drawLine(Offset(w * 0.45, h * 0.70), Offset(w * 0.55, h * 0.88), furrowPaint);
    canvas.drawLine(Offset(w * 0.65, h * 0.72), Offset(w * 0.75, h * 0.86), furrowPaint);

    // Sprouting Leaf Accent
    final leafPaint = Paint()
      ..color = AppColors.surface
      ..style = PaintingStyle.fill;

    final sproutCenter = Offset(w * 0.5, h * 0.58);
    canvas.drawCircle(sproutCenter, 4, leafPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Stylized topography illustration showing ridge, valley, and localized rain cloud.
class TopographyRainIllustration extends StatelessWidget {
  final double size;

  const TopographyRainIllustration({
    super.key,
    this.size = 140,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _TopographyRainPainter(),
      ),
    );
  }
}

class _TopographyRainPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Background circle container
    final bgPaint = Paint()
      ..color = AppColors.info100.withValues(alpha: 0.5)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(w / 2, h / 2), w * 0.48, bgPaint);

    final borderPaint = Paint()
      ..color = const Color(0xFFBCE0FD)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    canvas.drawCircle(Offset(w / 2, h / 2), w * 0.48, borderPaint);

    // High Elevation Mountain Ridge (Left)
    final ridgePaint = Paint()
      ..color = AppColors.ink700
      ..style = PaintingStyle.fill;

    final ridgePath = Path()
      ..moveTo(w * 0.08, h * 0.82)
      ..lineTo(w * 0.36, h * 0.42)
      ..lineTo(w * 0.62, h * 0.82)
      ..close();
    canvas.drawPath(ridgePath, ridgePaint);

    // Mountain peak snow/light accent
    final peakPaint = Paint()
      ..color = AppColors.surface.withValues(alpha: 0.7)
      ..style = PaintingStyle.fill;
    final peakPath = Path()
      ..moveTo(w * 0.36, h * 0.42)
      ..lineTo(w * 0.30, h * 0.52)
      ..lineTo(w * 0.42, h * 0.52)
      ..close();
    canvas.drawPath(peakPath, peakPaint);

    // Valley Agricultural Floor (Right)
    final valleyPaint = Paint()
      ..color = AppColors.primary600
      ..style = PaintingStyle.fill;

    final valleyPath = Path()
      ..moveTo(w * 0.50, h * 0.82)
      ..quadraticBezierTo(w * 0.72, h * 0.68, w * 0.92, h * 0.74)
      ..lineTo(w * 0.92, h * 0.90)
      ..lineTo(w * 0.50, h * 0.90)
      ..close();
    canvas.drawPath(valleyPath, valleyPaint);

    // Localized Rain Cloud over ridge
    final cloudPaint = Paint()
      ..color = AppColors.info600
      ..style = PaintingStyle.fill;

    canvas.drawCircle(Offset(w * 0.36, h * 0.30), w * 0.12, cloudPaint);
    canvas.drawCircle(Offset(w * 0.26, h * 0.32), w * 0.09, cloudPaint);
    canvas.drawCircle(Offset(w * 0.46, h * 0.32), w * 0.09, cloudPaint);

    // Raindrop Streaks under cloud
    final rainPaint = Paint()
      ..color = AppColors.info600
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;

    canvas.drawLine(Offset(w * 0.28, h * 0.44), Offset(w * 0.25, h * 0.52), rainPaint);
    canvas.drawLine(Offset(w * 0.36, h * 0.45), Offset(w * 0.33, h * 0.54), rainPaint);
    canvas.drawLine(Offset(w * 0.44, h * 0.44), Offset(w * 0.41, h * 0.52), rainPaint);

    // Gentle sun over valley (Right)
    final valleySunPaint = Paint()
      ..color = AppColors.sun500
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(w * 0.76, h * 0.45), w * 0.08, valleySunPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Subtle undulating sound wave indicator for audio playback.
class AudioWaveformIllustration extends StatelessWidget {
  final bool isPlaying;
  final Color color;

  const AudioWaveformIllustration({
    super.key,
    required this.isPlaying,
    this.color = AppColors.primary700,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 24,
      height: 16,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          _buildBar(isPlaying ? 8 : 4),
          _buildBar(isPlaying ? 16 : 8),
          _buildBar(isPlaying ? 12 : 5),
          _buildBar(isPlaying ? 14 : 7),
        ],
      ),
    );
  }

  Widget _buildBar(double height) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      width: 3,
      height: height,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(2),
      ),
    );
  }
}

/// Vector-rendered weather condition visual reflecting downscaled rainfall level.
class WeatherConditionIllustration extends StatelessWidget {
  final double rainfallMm;
  final double size;

  const WeatherConditionIllustration({
    super.key,
    required this.rainfallMm,
    this.size = 56,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _WeatherConditionPainter(rainfallMm: rainfallMm),
      ),
    );
  }
}

class _WeatherConditionPainter extends CustomPainter {
  final double rainfallMm;

  _WeatherConditionPainter({required this.rainfallMm});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    final isHeavy = rainfallMm >= 64.5;
    final isModerate = rainfallMm >= 7.6 && rainfallMm < 64.5;
    final isLight = rainfallMm > 0.0 && rainfallMm < 7.6;
    final isClear = rainfallMm == 0.0;

    // Background Container
    final bgPaint = Paint()
      ..color = isHeavy
          ? AppColors.danger100
          : isModerate
              ? AppColors.primary050
              : isLight
                  ? AppColors.info100
                  : AppColors.sun100
      ..style = PaintingStyle.fill;
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(0, 0, w, h), Radius.circular(w * 0.28)),
      bgPaint,
    );

    if (isClear) {
      // Warm glowing sun
      final sunCenter = Offset(w * 0.5, h * 0.5);
      final sunGlow = Paint()
        ..color = AppColors.sun500.withValues(alpha: 0.25)
        ..style = PaintingStyle.fill;
      canvas.drawCircle(sunCenter, w * 0.34, sunGlow);

      final sunPaint = Paint()
        ..color = AppColors.sun500
        ..style = PaintingStyle.fill;
      canvas.drawCircle(sunCenter, w * 0.22, sunPaint);

      // Subtle ray accents
      final rayPaint = Paint()
        ..color = AppColors.sun500
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2
        ..strokeCap = StrokeCap.round;
      canvas.drawLine(Offset(w * 0.5, h * 0.14), Offset(w * 0.5, h * 0.22), rayPaint);
      canvas.drawLine(Offset(w * 0.5, h * 0.78), Offset(w * 0.5, h * 0.86), rayPaint);
      canvas.drawLine(Offset(w * 0.14, h * 0.5), Offset(w * 0.22, h * 0.5), rayPaint);
      canvas.drawLine(Offset(w * 0.78, h * 0.5), Offset(w * 0.86, h * 0.5), rayPaint);
    } else {
      // Cloud Shape
      final cloudPaint = Paint()
        ..color = isHeavy
            ? const Color(0xFF6B7280)
            : isModerate
                ? AppColors.primary600
                : AppColors.info600
        ..style = PaintingStyle.fill;

      final cloudY = h * 0.42;
      canvas.drawCircle(Offset(w * 0.42, cloudY), w * 0.18, cloudPaint);
      canvas.drawCircle(Offset(w * 0.60, cloudY + 2), w * 0.14, cloudPaint);
      canvas.drawCircle(Offset(w * 0.28, cloudY + 4), w * 0.12, cloudPaint);

      final baseRect = RRect.fromRectAndRadius(
        Rect.fromLTWH(w * 0.24, cloudY + 4, w * 0.48, h * 0.16),
        Radius.circular(w * 0.08),
      );
      canvas.drawRRect(baseRect, cloudPaint);

      // Rain / Thunder accents
      if (isHeavy) {
        // Lightning bolt spark
        final sparkPaint = Paint()
          ..color = AppColors.warning600
          ..style = PaintingStyle.fill;
        final boltPath = Path()
          ..moveTo(w * 0.52, h * 0.58)
          ..lineTo(w * 0.44, h * 0.72)
          ..lineTo(w * 0.50, h * 0.72)
          ..lineTo(w * 0.46, h * 0.88)
          ..lineTo(w * 0.58, h * 0.70)
          ..lineTo(w * 0.52, h * 0.70)
          ..close();
        canvas.drawPath(boltPath, sparkPaint);

        // Angled rain streaks
        final rainPaint = Paint()
          ..color = AppColors.danger600
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeCap = StrokeCap.round;
        canvas.drawLine(Offset(w * 0.32, h * 0.68), Offset(w * 0.28, h * 0.84), rainPaint);
        canvas.drawLine(Offset(w * 0.68, h * 0.68), Offset(w * 0.64, h * 0.84), rainPaint);
      } else {
        // Raindrop streaks
        final rainPaint = Paint()
          ..color = isModerate ? AppColors.primary600 : AppColors.info600
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2
          ..strokeCap = StrokeCap.round;

        canvas.drawLine(Offset(w * 0.34, h * 0.68), Offset(w * 0.30, h * 0.82), rainPaint);
        canvas.drawLine(Offset(w * 0.48, h * 0.68), Offset(w * 0.44, h * 0.82), rainPaint);
        if (isModerate) {
          canvas.drawLine(Offset(w * 0.62, h * 0.68), Offset(w * 0.58, h * 0.82), rainPaint);
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant _WeatherConditionPainter oldDelegate) =>
      oldDelegate.rainfallMm != rainfallMm;
}

/// Lightweight horizontal gauge showing downscaled forecast position on IMD scale.
class RainfallGaugeIllustration extends StatelessWidget {
  final double rainfallMm;

  const RainfallGaugeIllustration({
    super.key,
    required this.rainfallMm,
  });

  @override
  Widget build(BuildContext context) {
    // Normalizing 0-100mm scale (clamped to 0.0 - 1.0)
    final progress = (rainfallMm / 100.0).clamp(0.0, 1.0);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: 14,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final totalWidth = constraints.maxWidth;
              final markerPos = (progress * totalWidth).clamp(6.0, totalWidth - 6.0);

              return Stack(
                alignment: Alignment.centerLeft,
                children: [
                  // Three-tier IMD gradient/segmented bar
                  Row(
                    children: [
                      // Light rain zone (0 - 7.5 mm => 7.5% of 100)
                      Expanded(
                        flex: 8,
                        child: Container(
                          height: 6,
                          decoration: const BoxDecoration(
                            color: AppColors.info100,
                            borderRadius: BorderRadius.horizontal(left: Radius.circular(3)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 2),
                      // Moderate rain zone (7.6 - 64.4 mm => 57% of 100)
                      Expanded(
                        flex: 57,
                        child: Container(
                          height: 6,
                          color: AppColors.primary100,
                        ),
                      ),
                      const SizedBox(width: 2),
                      // Heavy rain zone (64.5+ mm => 35% of 100)
                      Expanded(
                        flex: 35,
                        child: Container(
                          height: 6,
                          decoration: const BoxDecoration(
                            color: AppColors.danger100,
                            borderRadius: BorderRadius.horizontal(right: Radius.circular(3)),
                          ),
                        ),
                      ),
                    ],
                  ),
                  // Current Pointer Indicator
                  Positioned(
                    left: markerPos - 6,
                    child: Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: rainfallMm >= 64.5
                            ? AppColors.danger600
                            : rainfallMm >= 7.6
                                ? AppColors.primary700
                                : rainfallMm > 0
                                    ? AppColors.info600
                                    : AppColors.sun500,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppColors.surface, width: 2),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.12),
                            blurRadius: 3,
                            offset: const Offset(0, 1),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
        const SizedBox(height: 6),
        const Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'No/Light (<7.5mm)',
              style: TextStyle(fontSize: 10, color: AppColors.ink500, fontWeight: FontWeight.w500),
            ),
            Text(
              'Moderate (7.6-64.4mm)',
              style: TextStyle(fontSize: 10, color: AppColors.ink500, fontWeight: FontWeight.w500),
            ),
            Text(
              'Heavy (≥64.5mm)',
              style: TextStyle(fontSize: 10, color: AppColors.ink500, fontWeight: FontWeight.w500),
            ),
          ],
        ),
      ],
    );
  }
}


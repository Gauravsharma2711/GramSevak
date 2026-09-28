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

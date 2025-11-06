// lib/models/detection_result.dart
class DetectionResult {
  final String prediction;
  final double confidence;
  final bool isDrowsy;
  final String alertLevel;

  DetectionResult({
    required this.prediction,
    required this.confidence,
    required this.isDrowsy,
    required this.alertLevel,
  });

  factory DetectionResult.fromJson(Map<String, dynamic> json) {
    return DetectionResult(
      prediction: json['prediction'],
      confidence: json['confidence'].toDouble(),
      isDrowsy: json['is_drowsy'],
      alertLevel: json['alert_level'] ?? 'low',
    );
  }
}
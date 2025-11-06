// lib/models/session.dart
class Session {
  final int id;
  final String startTime;
  final String? endTime;
  final double distance;
  final int totalDetections;
  final int alerts;

  Session({
    required this.id,
    required this.startTime,
    this.endTime,
    required this.distance,
    required this.totalDetections,
    required this.alerts,
  });

  factory Session.fromJson(Map<String, dynamic> json) {
    return Session(
      id: json['id'],
      startTime: json['start_time'],
      endTime: json['end_time'],
      distance: (json['distance'] ?? 0).toDouble(),
      totalDetections: json['total_detections'] ?? 0,
      alerts: json['alerts'] ?? 0,
    );
  }

  Duration? get duration {
    if (endTime == null) return null;
    try {
      final start = DateTime.parse(startTime);
      final end = DateTime.parse(endTime!);
      return end.difference(start);
    } catch (e) {
      return null;
    }
  }

  double get safetyScore {
    if (totalDetections == 0) return 100.0;
    final drowsyRate = (alerts / totalDetections) * 100;
    return (100 - drowsyRate).clamp(0.0, 100.0);
  }
}


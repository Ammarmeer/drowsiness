// lib/models/recent_session.dart
class RecentSession {
  final int id;
  final String startTime;
  final String? endTime;
  final double distance;
  final int alerts;

  RecentSession({
    required this.id,
    required this.startTime,
    this.endTime,
    required this.distance,
    required this.alerts,
  });

  factory RecentSession.fromJson(Map<String, dynamic> json) {
    return RecentSession(
      id: json['id'],
      startTime: json['start_time'],
      endTime: json['end_time'],
      distance: (json['distance'] ?? 0).toDouble(),
      alerts: json['alerts'] ?? 0,
    );
  }
}


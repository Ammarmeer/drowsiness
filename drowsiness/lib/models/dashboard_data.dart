// lib/models/dashboard_data.dart
import 'package:drowsy_guard/models/recent_session.dart';

class DashboardData {
  final int totalSessions;
  final double totalDistance;
  final int totalAlerts;
  final double safetyScore;
  final List<RecentSession> recentSessions;

  DashboardData({
    required this.totalSessions,
    required this.totalDistance,
    required this.totalAlerts,
    required this.safetyScore,
    required this.recentSessions,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    final recentSessionsJson = json['recent_sessions'] as List? ?? [];
    final recentSessions = recentSessionsJson
        .map((sessionJson) => RecentSession.fromJson(sessionJson))
        .toList();

    return DashboardData(
      totalSessions: json['total_sessions'] ?? 0,
      totalDistance: (json['total_distance'] ?? 0).toDouble(),
      totalAlerts: json['total_alerts'] ?? 0,
      safetyScore: (json['safety_score'] ?? 100).toDouble(),
      recentSessions: recentSessions,
    );
  }
}


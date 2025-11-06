// lib/models/user.dart
class User {
  final int id;
  final String username;
  final String email;
  final String? phone;

  User({
    required this.id,
    required this.username,
    required this.email,
    this.phone,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'email': email,
      'phone': phone,
    };
  }

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      username: json['username'],
      email: json['email'],
      phone: json['phone'],
    );
  }
}


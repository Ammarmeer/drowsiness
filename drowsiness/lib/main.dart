import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:http/http.dart' as http;
import 'package:audioplayers/audioplayers.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final cameras = await availableCameras();
  final frontCamera = cameras.firstWhere(
    (camera) => camera.lensDirection == CameraLensDirection.front,
    orElse: () => cameras.first,
  );
  runApp(DrowsyGuardApp(camera: frontCamera));
}

class DrowsyGuardApp extends StatelessWidget {
  final CameraDescription camera;
  const DrowsyGuardApp({super.key, required this.camera});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DrowsyGuard',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.light,
        ),
      ),
      home: AuthWrapper(camera: camera),
    );
  }
}

// User model
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

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      username: json['username'],
      email: json['email'],
      phone: json['phone'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'email': email,
      'phone': phone,
    };
  }
}

// Auth wrapper
class AuthWrapper extends StatefulWidget {
  final CameraDescription camera;
  const AuthWrapper({super.key, required this.camera});

  @override
  State<AuthWrapper> createState() => _AuthWrapperState();
}

class _AuthWrapperState extends State<AuthWrapper> {
  User? _currentUser;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _checkLoginStatus();
  }

  Future<void> _checkLoginStatus() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final userJson = prefs.getString('current_user');
      
      if (userJson != null) {
        final userData = jsonDecode(userJson);
        setState(() {
          _currentUser = User.fromJson(userData);
          _isLoading = false;
        });
      } else {
        setState(() {
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('current_user');
    setState(() {
      _currentUser = null;
    });
  }

  void _onLoginSuccess(User user) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('current_user', jsonEncode(user.toJson()));
    setState(() {
      _currentUser = user;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        body: Container(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [Colors.blue.shade700, Colors.blue.shade900],
            ),
          ),
          child: const Center(
            child: CircularProgressIndicator(color: Colors.white),
          ),
        ),
      );
    }

    if (_currentUser == null) {
      return LoginScreen(onLoginSuccess: _onLoginSuccess);
    }

    return MainNavigationScreen(
      camera: widget.camera,
      user: _currentUser!,
      onLogout: _logout,
    );
  }
}

// Login Screen
class LoginScreen extends StatefulWidget {
  final Function(User) onLoginSuccess;
  const LoginScreen({super.key, required this.onLoginSuccess});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  static const String serverUrl = 'http://192.168.1.13:8000';
  
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  bool _obscurePassword = true;

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final response = await http.post(
        Uri.parse('$serverUrl/users/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': _usernameController.text,
          'password': _passwordController.text,
        }),
      );

      final data = jsonDecode(response.body);

      if (response.statusCode == 200 && data['success']) {
        final user = User.fromJson(data['user']);
        widget.onLoginSuccess(user);
      } else {
        _showError(data['detail'] ?? 'Login failed');
      }
    } catch (e) {
      _showError('Network error. Please check your connection.');
    }

    setState(() => _isLoading = false);
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.blue.shade700, Colors.blue.shade500],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Card(
                elevation: 20,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Logo
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [Colors.blue.shade400, Colors.blue.shade600],
                            ),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.local_taxi,
                            size: 48,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 24),
                        
                        // Title
                        const Text(
                          'DrowsyGuard',
                          style: TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                            color: Colors.black87,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Your AI-powered driving safety companion',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.grey.shade600,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 40),

                        // Username field
                        TextFormField(
                          controller: _usernameController,
                          decoration: InputDecoration(
                            labelText: 'Username',
                            prefixIcon: const Icon(Icons.person_outline),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please enter your username';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        // Password field
                        TextFormField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              icon: Icon(_obscurePassword ? Icons.visibility : Icons.visibility_off),
                              onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please enter your password';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 32),

                        // Login button
                        SizedBox(
                          width: double.infinity,
                          height: 56,
                          child: ElevatedButton(
                            onPressed: _isLoading ? null : _login,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.blue.shade600,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                            child: _isLoading
                                ? const CircularProgressIndicator(color: Colors.white)
                                : const Text(
                                    'Login',
                                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Sign up link
                        TextButton(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) => SignupScreen(
                                  onSignupSuccess: widget.onLoginSuccess,
                                ),
                              ),
                            );
                          },
                          child: RichText(
                            text: TextSpan(
                              text: "Don't have an account? ",
                              style: TextStyle(color: Colors.grey.shade600, fontSize: 16),
                              children: [
                                TextSpan(
                                  text: 'Sign up',
                                  style: TextStyle(
                                    color: Colors.blue.shade700,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }
}

// Signup Screen
class SignupScreen extends StatefulWidget {
  final Function(User) onSignupSuccess;
  const SignupScreen({super.key, required this.onSignupSuccess});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  static const String serverUrl = 'http://192.168.1.13:8000';
  
  final _formKey = GlobalKey<FormState>();
  final _usernameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _isLoading = false;
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;

  Future<void> _signup() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isLoading = true);

    try {
      final response = await http.post(
        Uri.parse('$serverUrl/users/register'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': _usernameController.text,
          'email': _emailController.text,
          'password': _passwordController.text,
          'phone': _phoneController.text.isEmpty ? null : _phoneController.text,
        }),
      );

      final data = jsonDecode(response.body);

      if (response.statusCode == 200 && data['success']) {
        await _autoLogin();
      } else {
        _showError(data['detail'] ?? 'Signup failed');
      }
    } catch (e) {
      _showError('Network error. Please check your connection.');
    }

    setState(() => _isLoading = false);
  }

  Future<void> _autoLogin() async {
    try {
      final response = await http.post(
        Uri.parse('$serverUrl/users/login'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': _usernameController.text,
          'password': _passwordController.text,
        }),
      );

      final data = jsonDecode(response.body);

      if (response.statusCode == 200 && data['success']) {
        final user = User.fromJson(data['user']);
        widget.onSignupSuccess(user);
      }
    } catch (e) {
      _showError('Account created but login failed. Please login manually.');
      Navigator.pop(context);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      extendBodyBehindAppBar: true,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Colors.green.shade600, Colors.green.shade400],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Card(
                elevation: 20,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Logo
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: [Colors.green.shade400, Colors.green.shade600],
                            ),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.person_add,
                            size: 48,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Title
                        const Text(
                          'Create Account',
                          style: TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                            color: Colors.black87,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Join DrowsyGuard for safer driving',
                          style: TextStyle(
                            fontSize: 16,
                            color: Colors.grey.shade600,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 40),

                        // Username field
                        TextFormField(
                          controller: _usernameController,
                          decoration: InputDecoration(
                            labelText: 'Username',
                            prefixIcon: const Icon(Icons.person_outline),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please enter a username';
                            }
                            if (value.length < 3) {
                              return 'Username must be at least 3 characters';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        // Email field
                        TextFormField(
                          controller: _emailController,
                          keyboardType: TextInputType.emailAddress,
                          decoration: InputDecoration(
                            labelText: 'Email',
                            prefixIcon: const Icon(Icons.email_outlined),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please enter your email';
                            }
                            if (!value.contains('@') || !value.contains('.')) {
                              return 'Please enter a valid email';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        // Password field
                        TextFormField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              icon: Icon(_obscurePassword ? Icons.visibility : Icons.visibility_off),
                              onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please enter a password';
                            }
                            if (value.length < 6) {
                              return 'Password must be at least 6 characters';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        // Confirm Password field
                        TextFormField(
                          controller: _confirmPasswordController,
                          obscureText: _obscureConfirmPassword,
                          decoration: InputDecoration(
                            labelText: 'Confirm Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            suffixIcon: IconButton(
                              icon: Icon(_obscureConfirmPassword ? Icons.visibility : Icons.visibility_off),
                              onPressed: () => setState(() => _obscureConfirmPassword = !_obscureConfirmPassword),
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return 'Please confirm your password';
                            }
                            if (value != _passwordController.text) {
                              return 'Passwords do not match';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        // Phone field (optional)
                        TextFormField(
                          controller: _phoneController,
                          keyboardType: TextInputType.phone,
                          decoration: InputDecoration(
                            labelText: 'Phone (Optional)',
                            prefixIcon: const Icon(Icons.phone_outlined),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                        ),
                        const SizedBox(height: 32),

                        // Signup button
                        SizedBox(
                          width: double.infinity,
                          height: 56,
                          child: ElevatedButton(
                            onPressed: _isLoading ? null : _signup,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green.shade600,
                              foregroundColor: Colors.white,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(16),
                              ),
                            ),
                            child: _isLoading
                                ? const CircularProgressIndicator(color: Colors.white)
                                : const Text(
                                    'Create Account',
                                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                          ),
                        ),
                        const SizedBox(height: 24),

                        // Login link
                        TextButton(
                          onPressed: () => Navigator.pop(context),
                          child: RichText(
                            text: TextSpan(
                              text: "Already have an account? ",
                              style: TextStyle(color: Colors.grey.shade600, fontSize: 16),
                              children: [
                                TextSpan(
                                  text: 'Login',
                                  style: TextStyle(
                                    color: Colors.green.shade700,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _phoneController.dispose();
    super.dispose();
  }
}

// Main Navigation
class MainNavigationScreen extends StatefulWidget {
  final CameraDescription camera;
  final User user;
  final VoidCallback onLogout;
  
  const MainNavigationScreen({
    super.key, 
    required this.camera, 
    required this.user,
    required this.onLogout,
  });

  @override
  State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
  int _currentIndex = 0;
  final GlobalKey<_DashboardScreenState> _dashboardKey = GlobalKey();

  @override
  Widget build(BuildContext context) {
    final screens = [
      DashboardScreen(
        key: _dashboardKey,
        user: widget.user, 
        onLogout: widget.onLogout,
      ),
      DrowsinessDetectionScreen(
        camera: widget.camera, 
        user: widget.user,
        onDetectionComplete: () {
          print('Detection completed callback called');
          // Force refresh dashboard
          Future.delayed(const Duration(milliseconds: 500), () {
            if (_dashboardKey.currentState != null) {
              print('Refreshing dashboard');
              _dashboardKey.currentState!.refreshDashboard();
            }
          });
        },
      ),
    ];

    return Scaffold(
      body: screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() => _currentIndex = index);
          // Also refresh dashboard when switching to it
          if (index == 0) {
            print('Switched to dashboard, refreshing');
            Future.delayed(const Duration(milliseconds: 100), () {
              if (_dashboardKey.currentState != null) {
                _dashboardKey.currentState!.refreshDashboard();
              }
            });
          }
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard),
            label: 'Dashboard',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.visibility),
            label: 'Detection',
          ),
        ],
      ),
    );
  }
}

// Dashboard Screen
class DashboardScreen extends StatefulWidget {
  final User user;
  final VoidCallback onLogout;
  
  const DashboardScreen({super.key, required this.user, required this.onLogout});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  static const String serverUrl = 'http://192.168.1.13:8000';
  Map<String, dynamic>? _dashboardData;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    print('Loading dashboard data for user ${widget.user.id}');
    setState(() => _isLoading = true);
    
    try {
      final response = await http.get(
        Uri.parse('$serverUrl/users/${widget.user.id}/dashboard'),
      );

      print('Dashboard API response: ${response.statusCode}');
      print('Dashboard API body: ${response.body}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success']) {
          print('Dashboard data loaded: $data');
          setState(() {
            _dashboardData = data['data'];
            _isLoading = false;
          });
          return;
        }
      }
    } catch (e) {
      print('Dashboard error: $e');
    }
    
    setState(() => _isLoading = false);
  }

  Future<void> refreshDashboard() async {
    print('Refresh dashboard called');
    await _loadDashboardData();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Welcome, ${widget.user.username}'),
        backgroundColor: Colors.blue.shade700,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              print('Manual refresh button pressed');
              refreshDashboard();
            },
          ),
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'logout') {
                widget.onLogout();
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout),
                    SizedBox(width: 8),
                    Text('Logout'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: refreshDashboard,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Stats Cards
                    Row(
                      children: [
                        Expanded(
                          child: _buildStatCard(
                            'Total Sessions',
                            '${_dashboardData?['total_sessions'] ?? 0}',
                            Icons.timeline,
                            Colors.blue,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _buildStatCard(
                            'Safety Score',
                            '${_dashboardData?['safety_score'] ?? 100}%',
                            Icons.security,
                            Colors.green,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: _buildStatCard(
                            'Total Detections',
                            '${_dashboardData?['total_detections'] ?? 0}',
                            Icons.visibility,
                            Colors.purple,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _buildStatCard(
                            'Total Alerts',
                            '${_dashboardData?['total_alerts'] ?? 0}',
                            Icons.warning,
                            Colors.orange,
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 24),

                    // Quick Actions
                    Card(
                      child: ListTile(
                        leading: const Icon(Icons.play_circle_filled, color: Colors.green, size: 40),
                        title: const Text('Start Detection', style: TextStyle(fontWeight: FontWeight.bold)),
                        subtitle: const Text('Begin monitoring your drowsiness'),
                        trailing: const Icon(Icons.arrow_forward_ios),
                        onTap: () {
                          final navState = context.findAncestorStateOfType<_MainNavigationScreenState>();
                          if (navState != null) {
                            navState.setState(() => navState._currentIndex = 1);
                          }
                        },
                      ),
                    ),

                    const SizedBox(height: 24),

                    // Recent Sessions
                    const Text(
                      'Recent Sessions',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 16),
                    ..._buildRecentSessions(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(
              value,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            Text(
              title,
              style: TextStyle(
                fontSize: 12,
                color: Colors.grey.shade600,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildRecentSessions() {
    final sessions = _dashboardData?['recent_sessions'] as List? ?? [];
    
    if (sessions.isEmpty) {
      return [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                Icon(Icons.history, size: 48, color: Colors.grey.shade400),
                const SizedBox(height: 16),
                Text(
                  'No sessions yet',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey.shade600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Start your first detection session to see history here',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey.shade500,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ];
    }

    return sessions.map<Widget>((session) {
      final alerts = session['alerts'] ?? 0;
      final totalDetections = session['total_detections'] ?? 0;
      
      return Card(
        margin: const EdgeInsets.only(bottom: 8),
        child: ListTile(
          leading: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: alerts > 0 ? Colors.red.shade50 : Colors.green.shade50,
              shape: BoxShape.circle,
            ),
            child: Icon(
              alerts > 0 ? Icons.warning : Icons.check_circle,
              color: alerts > 0 ? Colors.red : Colors.green,
              size: 20,
            ),
          ),
          title: Text('Session #${session['id']}'),
          subtitle: Text('$totalDetections detections • $alerts alerts'),
          trailing: Text(
            _formatDateTime(session['start_time']),
            style: TextStyle(
              color: Colors.grey.shade500,
              fontSize: 12,
            ),
          ),
        ),
      );
    }).toList();
  }

  String _formatDateTime(String? dateTime) {
    if (dateTime == null) return '';
    try {
      final date = DateTime.parse(dateTime);
      return '${date.day}/${date.month}';
    } catch (e) {
      return '';
    }
  }
}

// Detection Screen
class DrowsinessDetectionScreen extends StatefulWidget {
  final CameraDescription camera;
  final User user;
  final VoidCallback? onDetectionComplete;
  
  const DrowsinessDetectionScreen({
    super.key, 
    required this.camera, 
    required this.user,
    this.onDetectionComplete,
  });

  @override
  State<DrowsinessDetectionScreen> createState() => _DrowsinessDetectionScreenState();
}

class _DrowsinessDetectionScreenState extends State<DrowsinessDetectionScreen> 
    with TickerProviderStateMixin {
  static const String serverUrl = 'http://192.168.1.13:8000';
  
  late CameraController _cameraController;
  late Future<void> _initializeControllerFuture;
  late AudioPlayer _audioPlayer;
  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;
  
  bool _isDetecting = false;
  bool _isDrowsy = false;
  bool _isProcessing = false; // Add flag to prevent overlapping requests
  String _currentStatus = 'Ready to start detection';
  String _lastPrediction = '';
  double _lastConfidence = 0.0;
  int _detectionCount = 0;
  int _drowsyCount = 0;
  int? _currentSessionId;
  
  Timer? _detectionTimer;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
    _audioPlayer = AudioPlayer();
    _setupAnimations();
  }

  void _setupAnimations() {
    _pulseController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    _pulseAnimation = Tween<double>(
      begin: 1.0,
      end: 1.2,
    ).animate(CurvedAnimation(
      parent: _pulseController,
      curve: Curves.easeInOut,
    ));
  }

  void _initializeCamera() {
    _cameraController = CameraController(
      widget.camera,
      ResolutionPreset.low, // Reduced from medium to low for faster processing
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );
    _initializeControllerFuture = _cameraController.initialize();
  }

  Future<void> _startDetection() async {
    if (!_cameraController.value.isInitialized) return;

    try {
      final response = await http.post(
        Uri.parse('$serverUrl/sessions/start'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'user_id': widget.user.id}),
      );

      final data = jsonDecode(response.body);
      if (data['success']) {
        _currentSessionId = data['session_id'];
      }
    } catch (e) {
      print('Failed to start session: $e');
    }

    setState(() {
      _isDetecting = true;
      _currentStatus = 'Detection started - Stay alert!';
      _detectionCount = 0;
      _drowsyCount = 0;
    });

    // Reduced interval to 500ms for real-time detection
    _detectionTimer = Timer.periodic(
      const Duration(milliseconds: 500),
      (_) => _captureAndAnalyze(),
    );
  }

  Future<void> _stopDetection() async {
    _detectionTimer?.cancel();
    _pulseController.stop();
    await _audioPlayer.stop();

    if (_currentSessionId != null) {
      try {
        print('Ending session $_currentSessionId');
        final response = await http.post(
          Uri.parse('$serverUrl/sessions/$_currentSessionId/end'),
          headers: {'Content-Type': 'application/json'},
        );
        
        print('End session response: ${response.statusCode}');
        print('End session body: ${response.body}');
        
        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          if (data['success']) {
            print('Session ended successfully, calling callback');
            widget.onDetectionComplete?.call();
          }
        } else {
          print('Failed to end session: ${response.statusCode} - ${response.body}');
        }
      } catch (e) {
        print('Failed to end session: $e');
      }
    }
    
    setState(() {
      _isDetecting = false;
      _isDrowsy = false;
      _currentStatus = 'Detection stopped';
      _currentSessionId = null;
    });
  }

  Future<void> _captureAndAnalyze() async {
    // Skip if already processing or camera not ready
    if (!_cameraController.value.isInitialized || !_isDetecting || _isProcessing) return;

    _isProcessing = true;

    try {
      final image = await _cameraController.takePicture();
      final result = await _sendImageToBackend(image.path);
      
      if (result != null) {
        setState(() {
          _lastPrediction = result['prediction'] ?? 'unknown';
          _lastConfidence = (result['confidence'] ?? 0.0).toDouble();
          _detectionCount++;
          
          _isDrowsy = _lastPrediction.toLowerCase().contains('drowsy') && 
                     _lastConfidence > 0.6; // Reduced threshold for faster response
          
          if (_isDrowsy) {
            _drowsyCount++;
            _currentStatus = 'DROWSINESS DETECTED!';
            _handleDrowsinessDetection();
          } else {
            _currentStatus = 'Monitoring... Status: $_lastPrediction';
            _pulseController.stop();
          }
        });
      }
    } catch (e) {
      setState(() {
        _currentStatus = 'Error: $e';
      });
    } finally {
      _isProcessing = false;
    }
  }

  Future<void> _handleDrowsinessDetection() async {
    _pulseController.repeat(reverse: true);
    
    try {
      await _audioPlayer.play(AssetSource('sounds/alarm.mp3'));
    } catch (e) {
      print('Audio error: $e');
    }
    
    _showDrowsinessAlert();
  }

  Future<Map<String, dynamic>?> _sendImageToBackend(String imagePath) async {
    try {
      String endpoint = _currentSessionId != null 
          ? '$serverUrl/detect/$_currentSessionId'
          : '$serverUrl/predict_frame';
      
      var request = http.MultipartRequest('POST', Uri.parse(endpoint));
      request.files.add(await http.MultipartFile.fromPath('file', imagePath));
      
      // Reduced timeout for faster response
      final streamedResponse = await request.send().timeout(
        const Duration(seconds: 3), // Reduced from 10 to 3 seconds
      );
      
      final response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final jsonResponse = jsonDecode(response.body);
        if (jsonResponse['success'] == true) {
          return jsonResponse['data'];
        }
      }
      
      return null;
    } catch (e) {
      print('Backend error: $e');
      return null;
    }
  }

  void _showDrowsinessAlert() {
    if (!mounted) return;
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: const Text('DROWSINESS ALERT!'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.warning, size: 50, color: Colors.red),
            const SizedBox(height: 16),
            const Text('Drowsiness detected!'),
            const SizedBox(height: 8),
            const Text('Please take a break and pull over safely.'),
            const SizedBox(height: 12),
            Text('Confidence: ${(_lastConfidence * 100).toStringAsFixed(1)}%'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () async {
              await _audioPlayer.stop();
              _pulseController.stop();
              Navigator.pop(context);
            },
            child: const Text('I\'m Alert'),
          ),
          ElevatedButton(
            onPressed: () async {
              await _audioPlayer.stop();
              _pulseController.stop();
              Navigator.pop(context);
              _stopDetection();
            },
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Stop Detection'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _detectionTimer?.cancel();
    _cameraController.dispose();
    _audioPlayer.dispose();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Drowsiness Detection'),
        backgroundColor: _isDrowsy ? Colors.red : Colors.blue,
        foregroundColor: Colors.white,
      ),
      body: FutureBuilder<void>(
        future: _initializeControllerFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.done) {
            return Column(
              children: [
                // Camera Preview
                Expanded(
                  flex: 3,
                  child: Container(
                    margin: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: _isDrowsy ? Colors.red : Colors.grey,
                        width: 2,
                      ),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(10),
                      child: CameraPreview(_cameraController),
                    ),
                  ),
                ),
                
                // Status Card
                Card(
                  margin: const EdgeInsets.all(16),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      children: [
                        Text(
                          _currentStatus,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: _isDrowsy ? Colors.red : Colors.blue,
                          ),
                        ),
                        if (_isDetecting) ...[
                          const SizedBox(height: 16),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceAround,
                            children: [
                              Column(
                                children: [
                                  const Text('Detections'),
                                  Text(
                                    _detectionCount.toString(),
                                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                              Column(
                                children: [
                                  const Text('Alerts'),
                                  Text(
                                    _drowsyCount.toString(),
                                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                              Column(
                                children: [
                                  Text(_isProcessing ? 'Processing...' : 'Ready'),
                                  Text(
                                    _lastConfidence > 0 ? '${(_lastConfidence * 100).toStringAsFixed(0)}%' : '-',
                                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
                
                // Control Buttons
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      SizedBox(
                        width: double.infinity,
                        height: 56,
                        child: ElevatedButton(
                          onPressed: _isDetecting ? _stopDetection : _startDetection,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _isDetecting ? Colors.red : Colors.green,
                            foregroundColor: Colors.white,
                          ),
                          child: Text(
                            _isDetecting ? 'Stop Detection' : 'Start Detection',
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                          ),
                        ),
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: _captureAndAnalyze,
                        child: const Text('Test Single Frame'),
                      ),
                    ],
                  ),
                ),
              ],
            );
          } else {
            return const Center(
              child: CircularProgressIndicator(),
            );
          }
        },
      ),
    );
  }
}
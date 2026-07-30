import '../../../core/api_client.dart';

class AuthUser {
  const AuthUser({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
        id: json['id'] as String,
        email: json['email'] as String,
        firstName: json['first_name'] as String,
        lastName: json['last_name'] as String,
      );

  final String id;
  final String email;
  final String firstName;
  final String lastName;

  String get fullName => '$firstName $lastName';
}

class AuthRepository {
  AuthRepository(this._api);

  final ApiClient _api;

  Future<AuthUser> login(String email, String password) async {
    final data = await _api.post<Map<String, dynamic>>(
      '/auth/login',
      body: {
        'email': email,
        'password': password,
        'device_type': 'android',
      },
    );
    final tokens = data['tokens'] as Map<String, dynamic>;
    await _api.saveTokens(
      access: tokens['access_token'] as String,
      refresh: tokens['refresh_token'] as String,
    );
    return AuthUser.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<void> logout() => _api.clearTokens();
}

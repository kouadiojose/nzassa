/// Configuration d'environnement (injectée à la compilation).
class Env {
  static const apiUrl = String.fromEnvironment(
    'NZASSA_API_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );
  static const apiPrefix = '/api/v1';
}

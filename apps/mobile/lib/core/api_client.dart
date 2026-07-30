import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'env.dart';

/// Exception applicative portant le code d'erreur stable de l'API.
class ApiException implements Exception {
  ApiException(this.message, {this.code = 'UNKNOWN', this.statusCode});

  final String message;
  final String code;
  final int? statusCode;

  @override
  String toString() => message;
}

/// Client HTTP : jeton d'accès, rafraîchissement automatique sur 401,
/// et normalisation des erreurs de l'API.
class ApiClient {
  ApiClient({Dio? dio, FlutterSecureStorage? storage})
      : _dio = dio ?? Dio(BaseOptions(baseUrl: Env.apiUrl + Env.apiPrefix)),
        _storage = storage ?? const FlutterSecureStorage() {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _storage.read(key: 'access_token');
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          if (error.response?.statusCode == 401 &&
              error.requestOptions.extra['retried'] != true &&
              !error.requestOptions.path.contains('/auth/')) {
            final refreshed = await _tryRefresh();
            if (refreshed) {
              final options = error.requestOptions;
              options.extra['retried'] = true;
              final token = await _storage.read(key: 'access_token');
              options.headers['Authorization'] = 'Bearer $token';
              try {
                final response = await _dio.fetch<dynamic>(options);
                return handler.resolve(response);
              } on DioException catch (retryError) {
                return handler.next(retryError);
              }
            }
          }
          handler.next(error);
        },
      ),
    );
  }

  final Dio _dio;
  final FlutterSecureStorage _storage;

  Future<bool> _tryRefresh() async {
    final refreshToken = await _storage.read(key: 'refresh_token');
    if (refreshToken == null) return false;
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      final data = response.data?['data'] as Map<String, dynamic>?;
      if (data == null) return false;
      await saveTokens(
        access: data['access_token'] as String,
        refresh: data['refresh_token'] as String,
      );
      return true;
    } on DioException {
      await clearTokens();
      return false;
    }
  }

  Future<void> saveTokens({required String access, required String refresh}) async {
    await _storage.write(key: 'access_token', value: access);
    await _storage.write(key: 'refresh_token', value: refresh);
  }

  Future<void> clearTokens() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }

  Future<bool> get hasSession async => await _storage.read(key: 'access_token') != null;

  /// Exécute une requête et retourne le champ `data` de l'enveloppe standard.
  Future<T> request<T>(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
  }) async {
    try {
      final response = await _dio.request<Map<String, dynamic>>(
        path,
        data: body,
        queryParameters: query,
        options: Options(method: method),
      );
      return response.data?['data'] as T;
    } on DioException catch (error) {
      final payload = error.response?.data;
      if (payload is Map<String, dynamic>) {
        final err = payload['error'] as Map<String, dynamic>?;
        throw ApiException(
          payload['message'] as String? ?? 'Erreur réseau',
          code: err?['code'] as String? ?? 'UNKNOWN',
          statusCode: error.response?.statusCode,
        );
      }
      throw ApiException(
        'Connexion impossible — vérifiez votre réseau',
        code: 'NETWORK_ERROR',
      );
    }
  }

  Future<T> get<T>(String path, {Map<String, dynamic>? query}) =>
      request<T>('GET', path, query: query);

  Future<T> post<T>(String path, {Object? body}) => request<T>('POST', path, body: body);
}

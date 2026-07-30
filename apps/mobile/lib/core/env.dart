import 'package:flutter/foundation.dart';

/// Configuration d'environnement (injectée à la compilation).
///
/// URL par défaut selon la plateforme :
/// - Web (flutter run -d chrome) : http://localhost:8000 ;
/// - Android (émulateur) : http://10.0.2.2:8000 (= localhost de la machine hôte) ;
/// - iOS simulateur / desktop : http://localhost:8000.
/// Sur un téléphone physique, passer l'IP de la machine :
/// `flutter run --dart-define=NZASSA_API_URL=http://192.168.1.XX:8000`.
class Env {
  static const _defined = String.fromEnvironment('NZASSA_API_URL');

  static String get apiUrl {
    if (_defined.isNotEmpty) return _defined;
    if (kIsWeb) return 'http://localhost:8000';
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://localhost:8000';
  }

  static const apiPrefix = '/api/v1';
}

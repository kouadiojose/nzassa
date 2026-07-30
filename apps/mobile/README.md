# N'Zassa Business — Mobile (Flutter)

Application Android/iOS, architecture clean feature-first, offline-first.

## Démarrage

```bash
flutter create . --platforms=android,ios   # génère les dossiers de plateforme
flutter pub get

# Émulateur Android (URL par défaut : http://10.0.2.2:8000, rien à passer)
flutter run

# Test rapide dans Chrome (URL par défaut : http://localhost:8000)
# NB : le mode hors ligne (SQLite) est désactivé sur le web.
flutter run -d chrome

# Téléphone physique : IP de votre machine sur le même Wi-Fi
flutter run --dart-define=NZASSA_API_URL=http://192.168.1.XX:8000
```

Sur Android en HTTP local, autorisez le trafic clair dans
`android/app/src/main/AndroidManifest.xml` :
`<application android:usesCleartextTraffic="true" …>`.

## Architecture

- `lib/core/` : client API (Dio + refresh token), stockage sécurisé,
  base SQLite locale, file de synchronisation offline.
- `lib/features/<feature>/` : `data/` (modèles + repositories) et
  `presentation/` (écrans + providers Riverpod).

## Hors connexion

Les ventes, dépenses et clients créés hors ligne reçoivent un UUID local,
sont stockés dans la table `pending_operations` puis rejoués sur
`POST /api/v1/sync/push` (idempotent via `client_operation_id`).
Le catalogue et les clients sont mis en cache via `GET /api/v1/sync/pull`.

## Tests

```bash
flutter test
```

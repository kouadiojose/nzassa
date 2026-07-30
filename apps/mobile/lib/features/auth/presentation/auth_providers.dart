import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../data/auth_repository.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final authRepositoryProvider =
    Provider<AuthRepository>((ref) => AuthRepository(ref.watch(apiClientProvider)));

class AuthState {
  const AuthState({this.user, this.loading = false, this.error});

  final AuthUser? user;
  final bool loading;
  final String? error;

  bool get isAuthenticated => user != null;

  AuthState copyWith({AuthUser? user, bool? loading, String? error, bool clearUser = false}) =>
      AuthState(
        user: clearUser ? null : (user ?? this.user),
        loading: loading ?? false,
        error: error,
      );
}

class AuthNotifier extends Notifier<AuthState> {
  @override
  AuthState build() => const AuthState();

  Future<bool> login(String email, String password) async {
    state = state.copyWith(loading: true);
    try {
      final user = await ref.read(authRepositoryProvider).login(email, password);
      state = AuthState(user: user);
      return true;
    } on ApiException catch (error) {
      state = AuthState(error: error.message);
      return false;
    }
  }

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = const AuthState();
  }
}

final authStateProvider = NotifierProvider<AuthNotifier, AuthState>(AuthNotifier.new);

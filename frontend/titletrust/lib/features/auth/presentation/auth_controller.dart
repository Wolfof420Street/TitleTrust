import 'dart:async';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:titletrust/security/device_security_service.dart';
import 'package:titletrust/core/services/device_session_service.dart';
import '../data/auth_repository.dart';

part 'auth_controller.g.dart';

@riverpod
Stream<User?> authState(AuthStateRef ref) {
  return ref.watch(authRepositoryProvider).authStateChanges;
}

@riverpod
class AuthController extends _$AuthController {
  @override
  FutureOr<void> build() {}

  Future<void> signInWithGoogle() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final deviceSecurity = ref.read(deviceSecurityServiceProvider);
      final unlocked = await deviceSecurity.unlockWithBiometrics();
      if (!unlocked) {
        throw FirebaseAuthException(code: 'device-auth-required', message: 'Device authentication is required.');
      }
      final user = await ref.read(authRepositoryProvider).signInWithGoogle();
      if (user != null) {
        await ref.read(deviceSessionServiceProvider).register();
      }
    });
  }

  Future<void> signOut() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      await ref.read(deviceSessionServiceProvider).revoke();
      await ref.read(authRepositoryProvider).signOut();
    });
  }
}

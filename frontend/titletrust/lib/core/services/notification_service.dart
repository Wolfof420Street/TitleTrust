import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
// import 'package:flutter_riverpod/flutter_riverpod.dart';

// Top-level function for handling background messages
@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // If you're going to use other Firebase services in the background, such as Firestore,
  // make sure you call `Firebase.initializeApp` before using server other Firebase services.
  // await Firebase.initializeApp();

  debugPrint("Handling a background message: ${message.messageId}");

  // Persistence Logic even if app is closed
  if (message.data.containsKey('status')) {
    // Example: Update shared prefs key if tracking something
    // final prefs = await SharedPreferences.getInstance();
    // await prefs.setString('bg_status', message.data['status']);
  }
}

class NotificationService {
  final FirebaseMessaging _fcm = FirebaseMessaging.instance;
  final FirebaseFirestore _db = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  // Singleton pattern
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  Future<void> initialize() async {
    // 1. Set Background Handler
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

    // 2. Request Permission
    NotificationSettings settings = await _fcm.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    if (settings.authorizationStatus == AuthorizationStatus.authorized) {
      debugPrint('User granted permission');

      // 3. Get Token & Save
      String? token = await _fcm.getToken();
      if (token != null) {
        debugPrint("FCM Token: $token");
        await _saveToken(token);
      }

      // 4. Listen for Refreshes
      _fcm.onTokenRefresh.listen(_saveToken);

      // 5. Handle Interacted Messages (App Open from Terminated)
      RemoteMessage? initialMessage = await _fcm.getInitialMessage();
      if (initialMessage != null) {
        _handleMessage(initialMessage);
      }

      // 6. Handle Background -> Foreground transition
      FirebaseMessaging.onMessageOpenedApp.listen(_handleMessage);

      // 7. Handle Foreground Messages
      FirebaseMessaging.onMessage.listen((RemoteMessage message) {
        debugPrint('Got a message whilst in the foreground!');
        if (message.notification != null) {
          // Show local notification or update UI
        }
      });
    } else {
      debugPrint('User declined permission');
    }
  }

  void _handleMessage(RemoteMessage message) {
    if (message.data.containsKey('route')) {
      // Navigate to the deep link
      // Note: Currently simple print, in real app delegate to router
      debugPrint("Deep Link Requested: ${message.data['route']}");
    }
  }

  Future<void> _saveToken(String token) async {
    final user = _auth.currentUser;
    if (user != null) {
      // Write to Firestore as "Production Endpoint" equivalent for this architecture
      await _db.collection('users').doc(user.uid).set({
        'fcm_token': token,
        'platform': defaultTargetPlatform.toString(),
        'last_updated': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));

      // OPTIONAL: Call backend API if it existed
      // await Dio().post('/users/me/fcm', data: {'token': token});
    }
  }
}

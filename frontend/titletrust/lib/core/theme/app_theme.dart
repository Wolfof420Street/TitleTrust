import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AppTheme {
  // Brand Colors
  static const Color navyBlue = Color(0xFF001F3F);
  static const Color emeraldGreen = Color(0xFF2ECC71);

  // Material Theme (Android)
  static ThemeData get androidTheme {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: navyBlue,
        secondary: emeraldGreen,
        brightness: Brightness.light,
      ),
      scaffoldBackgroundColor: Colors.white,
    );
  }

  static ThemeData get androidDarkTheme {
    return ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: navyBlue,
        secondary: emeraldGreen,
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: Colors.black, // Pitch black for OLED
    );
  }

  // Cupertino Theme (iOS)
  static CupertinoThemeData get iosTheme {
    return const CupertinoThemeData(
      brightness: Brightness.light,
      primaryColor: CupertinoColors.systemIndigo, // Mapping Navy Blue-ish
      primaryContrastingColor: CupertinoColors.white,
      barBackgroundColor: null, // Allow translucency
      scaffoldBackgroundColor: CupertinoColors.systemBackground,
    );
  }

  static CupertinoThemeData get iosDarkTheme {
    return const CupertinoThemeData(
      brightness: Brightness.dark,
      primaryColor: CupertinoColors.systemIndigo,
      primaryContrastingColor: CupertinoColors.white,
      barBackgroundColor: null,
      scaffoldBackgroundColor: CupertinoColors.black, // Pitch black
    );
  }
}

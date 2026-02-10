import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AppTheme {
  // ==================== VERILAND Brand Colors ====================
  static const Color primaryGreen = Color(0xFF3D8F4E); // Map green
  static const Color accentOrange = Color(0xFFE67E33); // Route marker orange
  static const Color lightGreen = Color(0xFF7CB342); // Light map sections
  static const Color darkGreen = Color(0xFF1B5E20); // Dark map sections
  static const Color peachBackground = Color(0xFFE4C4A8); // Logo background
  static const Color darkOutline = Color(0xFF263238); // Dark borders/outlines
  static const Color white = Color(0xFFFFFFFF); // White accents

  // Additional semantic colors
  static const Color success = Color(0xFF4CAF50);
  static const Color warning = Color(0xFFFFA726);
  static const Color error = Color(0xFFE53935);
  static const Color info = Color(0xFF42A5F5);

  // Neutral colors
  static const Color grey50 = Color(0xFFFAFAFA);
  static const Color grey100 = Color(0xFFF5F5F5);
  static const Color grey200 = Color(0xFFEEEEEE);
  static const Color grey300 = Color(0xFFE0E0E0);
  static const Color grey400 = Color(0xFFBDBDBD);
  static const Color grey500 = Color(0xFF9E9E9E);
  static const Color grey600 = Color(0xFF757575);
  static const Color grey700 = Color(0xFF616161);
  static const Color grey800 = Color(0xFF424242);
  static const Color grey900 = Color(0xFF212121);

  // ==================== Material Theme (Android) ====================
  static ThemeData get androidTheme {
    return ThemeData(
      useMaterial3: true,

      // Color Scheme
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryGreen,
        primary: primaryGreen,
        secondary: accentOrange,
        tertiary: lightGreen,
        surface: white,
        background: grey50,
        error: error,
        brightness: Brightness.light,
      ),

      // Scaffold
      scaffoldBackgroundColor: grey50,

      // AppBar
      appBarTheme: const AppBarTheme(
        backgroundColor: primaryGreen,
        foregroundColor: white,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: white,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.15,
        ),
        iconTheme: IconThemeData(color: white),
      ),

      // Card
      cardTheme: const CardThemeData(
        color: white,
        elevation: 2,
        shadowColor: Color(0x1A263238), // darkOutline.withOpacity(0.1) approx
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          side: BorderSide(color: grey200, width: 1),
        ),
        margin: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),

      // ListTile
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        iconColor: primaryGreen,
        textColor: darkOutline,
        tileColor: white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),

      // Floating Action Button
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: accentOrange,
        foregroundColor: white,
        elevation: 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),

      // Bottom Navigation Bar
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: white,
        selectedItemColor: primaryGreen,
        unselectedItemColor: grey500,
        elevation: 8,
        type: BottomNavigationBarType.fixed,
        selectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.normal,
        ),
      ),

      // Navigation Bar (Material 3)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: white,
        indicatorColor: primaryGreen.withOpacity(0.2),
        elevation: 3,
        labelTextStyle: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: primaryGreen,
            );
          }
          return const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.normal,
            color: grey500,
          );
        }),
      ),

      // Bottom Sheet
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: white,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
      ),

      // Dialog
      dialogTheme: const DialogThemeData(
        backgroundColor: white,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
        ),
        titleTextStyle: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: darkOutline,
        ),
        contentTextStyle: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.normal,
          color: grey700,
        ),
      ),

      // Elevated Button
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryGreen,
          foregroundColor: white,
          elevation: 2,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Outlined Button
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: primaryGreen,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          side: const BorderSide(color: primaryGreen, width: 1.5),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Text Button
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: primaryGreen,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Icon Button
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: primaryGreen,
          iconSize: 24,
        ),
      ),

      // Chip
      chipTheme: ChipThemeData(
        backgroundColor: grey100,
        deleteIconColor: grey700,
        selectedColor: primaryGreen.withOpacity(0.2),
        secondarySelectedColor: accentOrange.withOpacity(0.2),
        labelStyle: const TextStyle(
          fontSize: 14,
          color: grey900,
        ),
        secondaryLabelStyle: const TextStyle(
          fontSize: 14,
          color: darkOutline,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: grey300, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: grey300, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: primaryGreen, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: error, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: error, width: 2),
        ),
        labelStyle: const TextStyle(
          fontSize: 16,
          color: grey700,
        ),
        hintStyle: const TextStyle(
          fontSize: 16,
          color: grey400,
        ),
        errorStyle: const TextStyle(
          fontSize: 12,
          color: error,
        ),
        prefixIconColor: grey500,
        suffixIconColor: grey500,
      ),

      // Checkbox
      checkboxTheme: CheckboxThemeData(
        fillColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return primaryGreen;
          }
          return grey400;
        }),
        checkColor: MaterialStateProperty.all(white),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),

      // Radio
      radioTheme: RadioThemeData(
        fillColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return primaryGreen;
          }
          return grey400;
        }),
      ),

      // Switch
      switchTheme: SwitchThemeData(
        thumbColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return primaryGreen;
          }
          return grey400;
        }),
        trackColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return primaryGreen.withOpacity(0.5);
          }
          return grey300;
        }),
      ),

      // Slider
      sliderTheme: SliderThemeData(
        activeTrackColor: primaryGreen,
        inactiveTrackColor: grey300,
        thumbColor: primaryGreen,
        overlayColor: primaryGreen.withOpacity(0.2),
        valueIndicatorColor: primaryGreen,
        valueIndicatorTextStyle: const TextStyle(
          color: white,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),

      // Progress Indicator
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: primaryGreen,
        linearTrackColor: grey200,
        circularTrackColor: grey200,
      ),

      // Snackbar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: darkOutline,
        contentTextStyle: const TextStyle(
          color: white,
          fontSize: 14,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        actionTextColor: accentOrange,
      ),

      // Divider
      dividerTheme: const DividerThemeData(
        color: grey300,
        thickness: 1,
        space: 1,
      ),

      // Tab Bar
      tabBarTheme: const TabBarThemeData(
        labelColor: primaryGreen,
        unselectedLabelColor: grey500,
        indicatorColor: primaryGreen,
        indicatorSize: TabBarIndicatorSize.tab,
        labelStyle: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.normal,
        ),
      ),

      // Drawer
      drawerTheme: const DrawerThemeData(
        backgroundColor: white,
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.horizontal(right: Radius.circular(16)),
        ),
      ),

      // Tooltip
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: darkOutline.withOpacity(0.9),
          borderRadius: BorderRadius.circular(4),
        ),
        textStyle: const TextStyle(
          color: white,
          fontSize: 12,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),

      // Badge
      badgeTheme: const BadgeThemeData(
        backgroundColor: error,
        textColor: white,
        textStyle: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),

      // Text Theme
      textTheme: const TextTheme(
        displayLarge: TextStyle(fontSize: 57, fontWeight: FontWeight.w400, color: darkOutline),
        displayMedium: TextStyle(fontSize: 45, fontWeight: FontWeight.w400, color: darkOutline),
        displaySmall: TextStyle(fontSize: 36, fontWeight: FontWeight.w400, color: darkOutline),
        headlineLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.w600, color: darkOutline),
        headlineMedium: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, color: darkOutline),
        headlineSmall: TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: darkOutline),
        titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w600, color: darkOutline),
        titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: darkOutline),
        titleSmall: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: darkOutline),
        bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, color: darkOutline),
        bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.w400, color: darkOutline),
        bodySmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w400, color: grey700),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: darkOutline),
        labelMedium: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: darkOutline),
        labelSmall: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: grey700),
      ),
    );
  }

  // ==================== Material Dark Theme (Android) ====================
  static ThemeData get androidDarkTheme {
    return ThemeData(
      useMaterial3: true,

      // Color Scheme
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryGreen,
        primary: lightGreen,
        secondary: accentOrange,
        tertiary: primaryGreen,
        surface: const Color(0xFF1A1A1A),
        background: Colors.black,
        error: error,
        brightness: Brightness.dark,
      ),

      // Scaffold
      scaffoldBackgroundColor: Colors.black,

      // AppBar
      appBarTheme: const AppBarTheme(
        backgroundColor: darkGreen,
        foregroundColor: white,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: white,
          fontSize: 20,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.15,
        ),
        iconTheme: IconThemeData(color: white),
      ),

      // Card
      cardTheme: const CardThemeData(
        color: Color(0xFF1A1A1A),
        elevation: 2,
        shadowColor: Color(0x80000000), // Colors.black.withOpacity(0.5) approx for const
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          side: BorderSide(color: Color(0x333D8F4E), width: 1), // primaryGreen with 0.2 opacity
        ),
        margin: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      ),

      // ListTile
      listTileTheme: ListTileThemeData(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        iconColor: lightGreen,
        textColor: white,
        tileColor: const Color(0xFF1A1A1A),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),

      // Floating Action Button
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: accentOrange,
        foregroundColor: white,
        elevation: 4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),

      // Bottom Navigation Bar
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: Color(0xFF1A1A1A),
        selectedItemColor: lightGreen,
        unselectedItemColor: grey500,
        elevation: 8,
        type: BottomNavigationBarType.fixed,
        selectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.normal,
        ),
      ),

      // Navigation Bar (Material 3)
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: const Color(0xFF1A1A1A),
        indicatorColor: lightGreen.withOpacity(0.3),
        elevation: 3,
        labelTextStyle: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: lightGreen,
            );
          }
          return const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.normal,
            color: grey500,
          );
        }),
      ),

      // Bottom Sheet
      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: Color(0xFF1A1A1A),
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
        ),
      ),

      // Dialog
      dialogTheme: const DialogThemeData(
        backgroundColor: Color(0xFF1A1A1A),
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(16)),
        ),
        titleTextStyle: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: white,
        ),
        contentTextStyle: TextStyle(
          fontSize: 16,
          fontWeight: FontWeight.normal,
          color: grey300,
        ),
      ),

      // Elevated Button
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryGreen,
          foregroundColor: white,
          elevation: 2,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Outlined Button
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: lightGreen,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          side: const BorderSide(color: lightGreen, width: 1.5),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Text Button
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: lightGreen,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
          textStyle: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            letterSpacing: 0.5,
          ),
        ),
      ),

      // Icon Button
      iconButtonTheme: IconButtonThemeData(
        style: IconButton.styleFrom(
          foregroundColor: lightGreen,
          iconSize: 24,
        ),
      ),

      // Chip
      chipTheme: ChipThemeData(
        backgroundColor: grey900,
        deleteIconColor: grey300,
        selectedColor: primaryGreen.withOpacity(0.3),
        secondarySelectedColor: accentOrange.withOpacity(0.3),
        labelStyle: const TextStyle(
          fontSize: 14,
          color: white,
        ),
        secondaryLabelStyle: const TextStyle(
          fontSize: 14,
          color: white,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),

      // Input Decoration
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xFF1A1A1A),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: grey700, width: 1),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: grey700, width: 1),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: lightGreen, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: error, width: 1),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: error, width: 2),
        ),
        labelStyle: const TextStyle(
          fontSize: 16,
          color: grey400,
        ),
        hintStyle: const TextStyle(
          fontSize: 16,
          color: grey600,
        ),
        errorStyle: const TextStyle(
          fontSize: 12,
          color: error,
        ),
        prefixIconColor: grey500,
        suffixIconColor: grey500,
      ),

      // Checkbox
      checkboxTheme: CheckboxThemeData(
        fillColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return lightGreen;
          }
          return grey600;
        }),
        checkColor: MaterialStateProperty.all(Colors.black),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
        ),
      ),

      // Radio
      radioTheme: RadioThemeData(
        fillColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return lightGreen;
          }
          return grey600;
        }),
      ),

      // Switch
      switchTheme: SwitchThemeData(
        thumbColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return lightGreen;
          }
          return grey600;
        }),
        trackColor: MaterialStateProperty.resolveWith((states) {
          if (states.contains(MaterialState.selected)) {
            return lightGreen.withOpacity(0.5);
          }
          return grey700;
        }),
      ),

      // Slider
      sliderTheme: SliderThemeData(
        activeTrackColor: lightGreen,
        inactiveTrackColor: grey700,
        thumbColor: lightGreen,
        overlayColor: lightGreen.withOpacity(0.3),
        valueIndicatorColor: lightGreen,
        valueIndicatorTextStyle: const TextStyle(
          color: Colors.black,
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),

      // Progress Indicator
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: lightGreen,
        linearTrackColor: grey800,
        circularTrackColor: grey800,
      ),

      // Snackbar
      snackBarTheme: SnackBarThemeData(
        backgroundColor: grey900,
        contentTextStyle: const TextStyle(
          color: white,
          fontSize: 14,
        ),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        actionTextColor: accentOrange,
      ),

      // Divider
      dividerTheme: const DividerThemeData(
        color: grey800,
        thickness: 1,
        space: 1,
      ),

      // Tab Bar
      tabBarTheme: const TabBarThemeData(
        labelColor: lightGreen,
        unselectedLabelColor: grey500,
        indicatorColor: lightGreen,
        indicatorSize: TabBarIndicatorSize.tab,
        labelStyle: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
        unselectedLabelStyle: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.normal,
        ),
      ),

      // Drawer
      drawerTheme: const DrawerThemeData(
        backgroundColor: Color(0xFF1A1A1A),
        elevation: 8,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.horizontal(right: Radius.circular(16)),
        ),
      ),

      // Tooltip
      tooltipTheme: TooltipThemeData(
        decoration: BoxDecoration(
          color: grey800.withOpacity(0.9),
          borderRadius: BorderRadius.circular(4),
        ),
        textStyle: const TextStyle(
          color: white,
          fontSize: 12,
        ),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      ),

      // Badge
      badgeTheme: const BadgeThemeData(
        backgroundColor: error,
        textColor: white,
        textStyle: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),

      // Text Theme
      textTheme: const TextTheme(
        displayLarge: TextStyle(fontSize: 57, fontWeight: FontWeight.w400, color: white),
        displayMedium: TextStyle(fontSize: 45, fontWeight: FontWeight.w400, color: white),
        displaySmall: TextStyle(fontSize: 36, fontWeight: FontWeight.w400, color: white),
        headlineLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.w600, color: white),
        headlineMedium: TextStyle(fontSize: 28, fontWeight: FontWeight.w600, color: white),
        headlineSmall: TextStyle(fontSize: 24, fontWeight: FontWeight.w600, color: white),
        titleLarge: TextStyle(fontSize: 22, fontWeight: FontWeight.w600, color: white),
        titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: white),
        titleSmall: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: white),
        bodyLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w400, color: white),
        bodyMedium: TextStyle(fontSize: 14, fontWeight: FontWeight.w400, color: white),
        bodySmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w400, color: grey400),
        labelLarge: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: white),
        labelMedium: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: white),
        labelSmall: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: grey400),
      ),
    );
  }

  // ==================== Cupertino Theme (iOS) ====================
  static CupertinoThemeData get iosTheme {
    return const CupertinoThemeData(
      brightness: Brightness.light,
      primaryColor: primaryGreen,
      primaryContrastingColor: white,
      barBackgroundColor: CupertinoColors.systemBackground,
      scaffoldBackgroundColor: grey50,
      textTheme: CupertinoTextThemeData(
        primaryColor: darkOutline,
        textStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 17,
          letterSpacing: -0.41,
          color: darkOutline,
        ),
        actionTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 17,
          letterSpacing: -0.41,
          color: primaryGreen,
        ),
        tabLabelTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 10,
          letterSpacing: -0.24,
          fontWeight: FontWeight.w500,
        ),
        navTitleTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 17,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.41,
          color: darkOutline,
        ),
        navLargeTitleTextStyle: TextStyle(
          fontFamily: '.SF Pro Display',
          fontSize: 34,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.41,
          color: darkOutline,
        ),
        pickerTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 21,
          fontWeight: FontWeight.w400,
          letterSpacing: -0.41,
        ),
        dateTimePickerTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 21,
          fontWeight: FontWeight.w400,
        ),
      ),
    );
  }

  static CupertinoThemeData get iosDarkTheme {
    return const CupertinoThemeData(
      brightness: Brightness.dark,
      primaryColor: lightGreen,
      primaryContrastingColor: white,
      barBackgroundColor: CupertinoColors.black,
      scaffoldBackgroundColor: CupertinoColors.black,
      textTheme: CupertinoTextThemeData(
        primaryColor: white,
        textStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 17,
          letterSpacing: -0.41,
          color: white,
        ),
        actionTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 17,
          letterSpacing: -0.41,
          color: lightGreen,
        ),
        tabLabelTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 10,
          letterSpacing: -0.24,
          fontWeight: FontWeight.w500,
        ),
        navTitleTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 17,
          fontWeight: FontWeight.w600,
          letterSpacing: -0.41,
          color: white,
        ),
        navLargeTitleTextStyle: TextStyle(
          fontFamily: '.SF Pro Display',
          fontSize: 34,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.41,
          color: white,
        ),
        pickerTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 21,
          fontWeight: FontWeight.w400,
          letterSpacing: -0.41,
        ),
        dateTimePickerTextStyle: TextStyle(
          fontFamily: '.SF Pro Text',
          fontSize: 21,
          fontWeight: FontWeight.w400,
        ),
      ),
    );
  }

  // ==================== Custom Text Styles ====================
  static const TextStyle displayLarge = TextStyle(
    fontSize: 57,
    fontWeight: FontWeight.w400,
    color: darkOutline,
    letterSpacing: -0.25,
  );

  static const TextStyle displayMedium = TextStyle(
    fontSize: 45,
    fontWeight: FontWeight.w400,
    color: darkOutline,
  );

  static const TextStyle displaySmall = TextStyle(
    fontSize: 36,
    fontWeight: FontWeight.w400,
    color: darkOutline,
  );

  static const TextStyle headlineLarge = TextStyle(
    fontSize: 32,
    fontWeight: FontWeight.w600,
    color: darkOutline,
  );

  static const TextStyle headlineMedium = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.w600,
    color: darkOutline,
  );

  static const TextStyle headlineSmall = TextStyle(
    fontSize: 24,
    fontWeight: FontWeight.w600,
    color: darkOutline,
  );

  static const TextStyle titleLarge = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.w600,
    color: darkOutline,
    letterSpacing: 0.15,
  );

  static const TextStyle titleMedium = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    color: darkOutline,
    letterSpacing: 0.15,
  );

  static const TextStyle titleSmall = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: darkOutline,
    letterSpacing: 0.1,
  );

  static const TextStyle bodyLarge = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: darkOutline,
    letterSpacing: 0.5,
  );

  static const TextStyle bodyMedium = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: darkOutline,
    letterSpacing: 0.25,
  );

  static const TextStyle bodySmall = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w400,
    color: grey700,
    letterSpacing: 0.4,
  );

  static const TextStyle labelLarge = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: darkOutline,
    letterSpacing: 0.1,
  );

  static const TextStyle labelMedium = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w600,
    color: darkOutline,
    letterSpacing: 0.5,
  );

  static const TextStyle labelSmall = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w600,
    color: grey700,
    letterSpacing: 0.5,
  );

  // Custom branded styles
  static const TextStyle brandHeadline = TextStyle(
    fontSize: 28,
    fontWeight: FontWeight.bold,
    color: primaryGreen,
    letterSpacing: 0.5,
  );

  static const TextStyle brandSubheadline = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: accentOrange,
    letterSpacing: 0.25,
  );

  static const TextStyle captionStyle = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.normal,
    color: grey600,
    letterSpacing: 0.4,
  );

  static const TextStyle overlineStyle = TextStyle(
    fontSize: 10,
    fontWeight: FontWeight.w600,
    color: grey700,
    letterSpacing: 1.5,
  );

  // ==================== Box Decorations ====================
  static BoxDecoration cardDecoration = BoxDecoration(
    color: white,
    borderRadius: BorderRadius.circular(12),
    border: Border.all(color: grey200, width: 1),
    boxShadow: [
      BoxShadow(
        color: darkOutline.withOpacity(0.1),
        blurRadius: 8,
        offset: const Offset(0, 2),
      ),
    ],
  );

  static BoxDecoration cardDecorationDark = BoxDecoration(
    color: const Color(0xFF1A1A1A),
    borderRadius: BorderRadius.circular(12),
    border: Border.all(color: primaryGreen.withOpacity(0.2), width: 1),
    boxShadow: [
      BoxShadow(
        color: Colors.black.withOpacity(0.3),
        blurRadius: 8,
        offset: const Offset(0, 2),
      ),
    ],
  );

  static BoxDecoration elevatedCardDecoration = BoxDecoration(
    color: white,
    borderRadius: BorderRadius.circular(16),
    border: Border.all(color: grey200, width: 1),
    boxShadow: [
      BoxShadow(
        color: darkOutline.withOpacity(0.15),
        blurRadius: 16,
        offset: const Offset(0, 4),
      ),
    ],
  );

  static const BoxDecoration primaryGradient = BoxDecoration(
    gradient:  LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        primaryGreen,
        lightGreen,
      ],
    ),
    borderRadius: BorderRadius.all(Radius.circular(12)),
  );

  static const BoxDecoration accentGradient = BoxDecoration(
    gradient:  LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: [
        accentOrange,
        warning,
      ],
    ),
    borderRadius: BorderRadius.all(Radius.circular(12)),
  );

  // ==================== Spacing Constants ====================
  static const double spacingXS = 4.0;
  static const double spacingS = 8.0;
  static const double spacingM = 16.0;
  static const double spacingL = 24.0;
  static const double spacingXL = 32.0;
  static const double spacingXXL = 48.0;

  // ==================== Border Radius Constants ====================
  static const double radiusS = 4.0;
  static const double radiusM = 8.0;
  static const double radiusL = 12.0;
  static const double radiusXL = 16.0;
  static const double radiusRound = 24.0;
  static const double radiusCircle = 999.0;

  // ==================== Icon Sizes ====================
  static const double iconSizeXS = 16.0;
  static const double iconSizeS = 20.0;
  static const double iconSizeM = 24.0;
  static const double iconSizeL = 32.0;
  static const double iconSizeXL = 48.0;

  // ==================== Animation Durations ====================
  static const Duration animationFast = Duration(milliseconds: 150);
  static const Duration animationNormal = Duration(milliseconds: 300);
  static const Duration animationSlow = Duration(milliseconds: 500);
}

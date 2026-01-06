import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AdaptiveVerdictCard extends StatelessWidget {
  final Widget child;
  final bool isCritical;

  const AdaptiveVerdictCard({
    super.key,
    required this.child,
    required this.isCritical,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    // Determine colors based on criticality and theme brightness
    Color backgroundColor;
    Color borderColor;

    if (isCritical) {
      if (isDark) {
        backgroundColor = Colors.red.shade900.withOpacity(0.5); // Dark Red for Dark Mode
        borderColor = Colors.redAccent;
      } else {
        backgroundColor = Colors.red.shade50; // Light Red for Light Mode
        borderColor = Colors.red;
      }
    } else {
      if (isDark) {
        backgroundColor = Colors.green.shade900.withOpacity(0.5); // Dark Green for Dark Mode
        borderColor = Colors.greenAccent;
      } else {
        backgroundColor = Colors.green.shade50; // Light Green for Light Mode
        borderColor = Colors.green;
      }
    }

    if (Platform.isIOS) {
      return Container(
        decoration: BoxDecoration(
          color: CupertinoColors.systemBackground.resolveFrom(context),
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: CupertinoColors.systemGrey.withOpacity(0.2),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
          border: Border.all(
            color: borderColor.withOpacity(0.5),
            width: 1,
          ),
        ),
        child: child,
      );
    } else {
      return Card(
        color: backgroundColor,
        elevation: 4,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12), side: BorderSide(color: borderColor, width: 0.5)),
        child: child,
      );
    }
  }
}

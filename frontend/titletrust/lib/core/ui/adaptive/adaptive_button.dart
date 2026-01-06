import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AdaptiveButton extends StatelessWidget {
  final VoidCallback onPressed;
  final Widget child;

  const AdaptiveButton({
    super.key,
    required this.onPressed,
    required this.child,
  });

  @override
  Widget build(BuildContext context) {
    if (Platform.isIOS) {
      return CupertinoButton.filled(
        onPressed: onPressed,
        child: child,
      );
    } else {
      return FilledButton(
        onPressed: onPressed,
        child: child,
      );
    }
  }
}

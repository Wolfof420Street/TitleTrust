import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AdaptiveAppBar extends StatelessWidget implements ObstructingPreferredSizeWidget {
  final String title;
  final List<Widget>? actions;
  final Widget? leading;

  const AdaptiveAppBar({
    super.key,
    required this.title,
    this.actions,
    this.leading,
  });

  @override
  Widget build(BuildContext context) {
    if (Platform.isIOS) {
      return CupertinoNavigationBar(
        middle: Text(title),
        trailing: actions != null && actions!.isNotEmpty
            ? Row(
                mainAxisSize: MainAxisSize.min,
                children: actions!,
              )
            : null,
        leading: leading,
        backgroundColor: null, // Transparent for blur effect
      );
    } else {
      return AppBar(
        title: Text(title),
        actions: actions,
        leading: leading,
      );
    }
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  bool shouldFullyObstruct(BuildContext context) {
    if (Platform.isIOS) {
      return true; // Typical for CupertinoNavigationBar with blur
    }
    return false;
  }
}

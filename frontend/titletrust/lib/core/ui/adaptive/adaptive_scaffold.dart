import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AdaptiveScaffold extends StatelessWidget {
  final Widget body;
  final ObstructingPreferredSizeWidget? appBar;
  final Widget? floatingActionButton;
  final Color? backgroundColor;

  const AdaptiveScaffold({
    super.key,
    required this.body,
    this.appBar,
    this.floatingActionButton,
    this.backgroundColor,
  });

  @override
  Widget build(BuildContext context) {
    if (Platform.isIOS) {
      return CupertinoPageScaffold(
        navigationBar: appBar as CupertinoNavigationBar?,
        backgroundColor: backgroundColor,
        child: floatingActionButton != null
            ? Stack(
                children: [
                  body,
                  Positioned(
                    bottom: 16,
                    right: 16,
                    child: SafeArea(child: floatingActionButton!),
                  ),
                ],
              )
            : body,
      );
    } else {
      return Scaffold(
        appBar: appBar as PreferredSizeWidget?,
        body: body,
        floatingActionButton: floatingActionButton,
        backgroundColor: backgroundColor,
      );
    }
  }
}

import 'dart:io';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class AdaptiveSpinner extends StatelessWidget {
  final Color? color;

  const AdaptiveSpinner({super.key, this.color});

  @override
  Widget build(BuildContext context) {
    if (Platform.isIOS) {
      return const CupertinoActivityIndicator();
    } else {
      return CircularProgressIndicator(
        color: color,
      );
    }
  }
}

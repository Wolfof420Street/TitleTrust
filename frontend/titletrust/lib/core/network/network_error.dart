class NetworkError implements Exception {
  final String message;
  final int? statusCode;

  const NetworkError(this.message, {this.statusCode});

  @override
  String toString() => message;
}

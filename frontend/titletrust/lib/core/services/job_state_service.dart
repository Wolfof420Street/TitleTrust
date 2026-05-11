import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'secure_storage_service.dart';

final jobStateServiceProvider = Provider<JobStateService>((ref) {
  return JobStateService(ref.watch(secureStorageServiceProvider));
});

class JobStateService {
  final SecureStorageService _storage;
  static const String _activeJobIdKey = 'active_job_id';
  static const String _jobStatusKey = 'job_status';

  JobStateService(this._storage);

  // Save the active job ID when a new investigation starts
  Future<void> setActiveJob(String jobId) async {
    await _storage.write(_activeJobIdKey, jobId);
    await _storage.write(_jobStatusKey, 'running');
  }

  // Retrieve the active active job ID (if any)
  Future<String?> getActiveJobId() => _storage.read(_activeJobIdKey);

  // Clear the job state when completed or cancelled
  Future<void> clearJob() async {
    await _storage.delete(_activeJobIdKey);
    await _storage.delete(_jobStatusKey);
  }

  // Update status
  Future<void> updateStatus(String status) async {
    await _storage.write(_jobStatusKey, status);
  }
}

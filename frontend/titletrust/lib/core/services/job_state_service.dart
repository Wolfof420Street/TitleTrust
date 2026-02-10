import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final jobStateServiceProvider = Provider<JobStateService>((ref) {
  return JobStateService();
});

class JobStateService {
  static const String _activeJobIdKey = 'active_job_id';
  static const String _jobStatusKey = 'job_status';

  // Save the active job ID when a new investigation starts
  Future<void> setActiveJob(String jobId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_activeJobIdKey, jobId);
    await prefs.setString(_jobStatusKey, 'running');
  }

  // Retrieve the active active job ID (if any)
  Future<String?> getActiveJobId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_activeJobIdKey);
  }

  // Clear the job state when completed or cancelled
  Future<void> clearJob() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_activeJobIdKey);
    await prefs.remove(_jobStatusKey);
  }

  // Update status
  Future<void> updateStatus(String status) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_jobStatusKey, status);
  }
}

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:titletrust/core/ui/adaptive/adaptive_app_bar.dart';
import 'package:titletrust/core/ui/adaptive/adaptive_scaffold.dart';
import 'package:titletrust/features/investigation/data/marathon_service.dart';
import 'package:titletrust/features/investigation/presentation/investigation_screen.dart';
import 'package:titletrust/core/services/job_state_service.dart';

class MarathonStartScreen extends ConsumerStatefulWidget {
  const MarathonStartScreen({super.key});

  @override
  ConsumerState<MarathonStartScreen> createState() => _MarathonStartScreenState();
}

class _MarathonStartScreenState extends ConsumerState<MarathonStartScreen> {
  bool _isLoading = false;
  File? _selectedFile;

  Future<void> _pickImage() async {
    final picker = ImagePicker();
    final pickedFile = await picker.pickImage(source: ImageSource.gallery);

    if (pickedFile != null) {
      setState(() {
        _selectedFile = File(pickedFile.path);
      });
    }
  }

  Future<void> _startMarathon() async {
    if (_selectedFile == null) return;

    setState(() => _isLoading = true);

    try {
      final result = await ref.read(marathonServiceProvider).startInvestigation(_selectedFile!);

      // PERSIST JOB STATE
      await ref.read(jobStateServiceProvider).setActiveJob(result.sessionId);

      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => InvestigationScreen(sessionId: result.sessionId)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Error: $e")));
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AdaptiveScaffold(
      appBar: const AdaptiveAppBar(title: "Autonomous Due Diligence"),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              "Initiate Land Audit",
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            const Text(
              "Upload a clear image of the Title Deed. The Autonomous Agent will recursively check registry records, gazette notices, and court cases.",
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 16, color: Colors.grey),
            ),
            const SizedBox(height: 40),

            // Upload Area
            GestureDetector(
              onTap: _pickImage,
              child: Container(
                height: 200,
                decoration: BoxDecoration(
                  color: Colors.grey.shade100,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.grey.shade300, width: 2),
                ),
                child: _selectedFile == null
                    ? const Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.cloud_upload_outlined, size: 64, color: Colors.blueGrey),
                          SizedBox(height: 10),
                          Text("Tap to Select Title Deed Image"),
                        ],
                      )
                    : ClipRRect(
                        borderRadius: BorderRadius.circular(14),
                        child: Image.file(_selectedFile!, fit: BoxFit.cover, width: double.infinity),
                      ),
              ),
            ),

            const Spacer(),

            // Action Button
            SizedBox(
              height: 56,
              child: ElevatedButton(
                onPressed: (_selectedFile != null && !_isLoading) ? _startMarathon : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.black,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                child: _isLoading
                    ? const CircularProgressIndicator(color: Colors.white)
                    : const Text("START INVESTIGATION", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              ),
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}

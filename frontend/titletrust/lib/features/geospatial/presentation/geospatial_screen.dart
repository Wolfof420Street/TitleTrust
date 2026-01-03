import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:permission_handler/permission_handler.dart';
import 'geospatial_controller.dart';

// Helper provider to get available cameras
final camerasProvider = FutureProvider<List<CameraDescription>>((ref) async {
  return await availableCameras();
});

class GeospatialScreen extends ConsumerStatefulWidget {
  const GeospatialScreen({super.key});

  @override
  ConsumerState<GeospatialScreen> createState() => _GeospatialScreenState();
}

class _GeospatialScreenState extends ConsumerState<GeospatialScreen> {
  CameraController? _controller;
  bool _isCameraInitialized = false;

  @override
  void initState() {
    super.initState();
    _initCamera();
    _requestPermissions();
  }

  Future<void> _requestPermissions() async {
    await [Permission.camera, Permission.location].request();
  }

  Future<void> _initCamera() async {
    final cameras = await ref.read(camerasProvider.future);
    if (cameras.isEmpty) return;

    // Use the first camera (usually back)
    _controller = CameraController(
      cameras.first,
      ResolutionPreset.medium,
    );

    await _controller!.initialize();
    if (!mounted) return;
    setState(() {
      _isCameraInitialized = true;
    });
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _captureAndVerify() async {
    if (_controller == null || !_controller!.value.isInitialized) return;

    try {
      final image = await _controller!.takePicture();
      // Pass to controller
      await ref.read(geospatialControllerProvider.notifier).performVerification(image);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(geospatialControllerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Geospatial Reality Check')),
      body: Column(
        children: [
          // Camera Preview Area
          Expanded(
            flex: 2,
            child: Container(
              color: Colors.black,
              child: _isCameraInitialized
                  ? CameraPreview(_controller!)
                  : const Center(child: CircularProgressIndicator(color: Colors.white)),
            ),
          ),

          // Controls & Results Area
          Expanded(
            flex: 1,
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: state.when(
                data: (result) {
                  if (result == null) {
                    return Center(
                      child: ElevatedButton.icon(
                        onPressed: _captureAndVerify,
                        icon: const Icon(Icons.camera_alt, size: 32),
                        label: const Text('VERIFY REALITY'),
                        style: ElevatedButton.styleFrom(
                          minimumSize: const Size(200, 60),
                          backgroundColor: Colors.blueAccent,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    );
                  }

                  final isCritical = result.riskLevel == 'CRITICAL' || result.riskLevel == 'HIGH';

                  return Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        isCritical ? Icons.cancel : Icons.check_circle,
                        color: isCritical ? Colors.red : Colors.green,
                        size: 64,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Risk Level: ${result.riskLevel}',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        result.satelliteAnalysisResult,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 16),
                      ),
                      const SizedBox(height: 16),
                      TextButton(
                          onPressed: () => ref.invalidate(geospatialControllerProvider),
                          child: const Text('Check Another Location'))
                    ],
                  );
                },
                error: (err, stack) => Center(child: Text('Error: $err', style: const TextStyle(color: Colors.red))),
                loading: () => const Center(
                    child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text("Analyzing Visuals vs Satellite Data...")
                  ],
                )),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

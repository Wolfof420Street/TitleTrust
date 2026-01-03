# TitleTrust

TitleTrust is a Flutter application designed for secure and reliable title verification and auditing. It leverages forensic analysis and geospatial verification to ensure the authenticity of assets and sites.

## Features

### 🔍 Forensic Audit
- **Document Upload**: Securely upload documents for forensic analysis.
- **Audit Findings**: View detailed status and findings of audit requests.
- **State Management**: Robust handling of audit states using Riverpod.

### 📍 Geospatial Verification
- **Site Verification**: Verify physical locations using GPS coordinates and camera capture.
- **Risk Assessment**: automated risk analysis based on satellite data and site checks.
- **Interactive Maps**: (Integration with Google Maps - *implied by dependencies*).

## Tech Stack

This project is built with a modern Flutter stack:

- **Framework**: [Flutter](https://flutter.dev/)
- **State Management**: [Riverpod](https://riverpod.dev/) (w/ Code Generation)
- **Networking**: [Dio](https://pub.dev/packages/dio)
- **Data Class Generation**: [Freezed](https://pub.dev/packages/freezed) & [JSON Serializable](https://pub.dev/packages/json_serializable)
- **Maps**: [Google Maps Flutter](https://pub.dev/packages/google_maps_flutter)
- **Camera & Location**: `image_picker`, `geolocator`

## Getting Started

### Prerequisites
- Flutter SDK (Latest Stable)
- Android Studio / VS Code with Flutter extensions
- Android Emulator or Physical Device

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd titletrust
   ```

2. **Install dependencies**
   ```bash
   flutter pub get
   ```

3. **Generate code**
   This project uses code generation for Riverpod and Freezed.
   ```bash
   dart run build_runner build --delete-conflicting-outputs
   ```

### Running the App

Ensure your backend server is running (default configuration points to `http://10.0.2.2:8000` for Android Emulator).

```bash
flutter run
```

## Project Structure

```
lib/
├── core/               # Core utilities (Networking, etc.)
├── features/           # Feature-based modules
│   ├── forensic/       # Forensic Audit feature
│   └── geospatial/     # Geospatial Verification feature
└── main.dart           # Application entry point
```

## Linting & Analysis

The project follows strict linting rules. To include code generation in analysis checks without noise, `deprecated_member_use` is suppressed for generated files in `analysis_options.yaml`.

```bash
flutter analyze
```

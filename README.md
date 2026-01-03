# TitleTrust

**TitleTrust** is a comprehensive solution for secure and reliable land title verification and auditing. By combining advanced forensic analysis with geospatial technology, TitleTrust provides a robust platform for detecting fraud and verifying asset authenticity.

## Project Structure

The project is divided into two main components:

*   **[Frontend (Flutter)](frontend/titletrust/README.md)**: A cross-platform mobile application built with Flutter, providing the user interface for document uploads, site verification, and audit results.
*   **[Backend (FastAPI)](backend/README.md)**: A high-performance python backend powered by FastAPI, handling the AI-driven forensic analysis (Vertex AI) and geospatial verification (Google Maps Platform).

```
TitleTrust/
├── backend/            # FastAPI Server (Python)
├── frontend/           # Flutter Mobile App (Dart)
├── tests/              # Integration Tests
├── requirements.txt    # Backend Dependencies
└── verify_titletrust.py # Verification Script
```

## Quick Start

To run the full stack locally, you will need two terminal sessions.

### 1. Start the Backend
Navigate to the root directory and run:

```bash
# Create/Activate Virtual Env
python -m venv venv
source venv/bin/activate

# Install Deps
pip install -r requirements.txt

# Run Server
uvicorn backend.main:app --reload
```
*The backend runs on `http://localhost:8000`*

### 2. Start the Frontend
Navigate to the frontend directory:

```bash
cd frontend/titletrust

# Get Deps
flutter pub get

# Generate Code
dart run build_runner build --delete-conflicting-outputs

# Run App  
flutter run
```

## Documentation

*   [AI Land Fraud Verification Plan](AI%20Land%20Fraud%20Verification%20Plan.pdf): Detailed project proposal and architecture plan.
*   [Frontend Documentation](frontend/titletrust/README.md)
*   [Backend Documentation](backend/README.md)

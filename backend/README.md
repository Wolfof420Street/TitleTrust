# TitleTrust Backend

The backend for TitleTrust is a high-performance **FastAPI** application that powers the forensic and geospatial verification engines. It integrates with Google Cloud Vertex AI (Gemini) and Google Maps Platform to provide real-time auditing and analysis.

## Features

- **Forensic Engine**: analyzing "Deal Packs" (Title Deeds, Green Cards, etc.) using AI to detect fraud and inconsistencies.
- **Geospatial Engine**: Verifies physical site locations by cross-referencing uploaded site photos with satellite imagery using Vision-Map Sync.
- **FastAPI**: Asynchronous, high-speed API endpoints.

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **AI/ML**: [Google Cloud Vertex AI](https://cloud.google.com/vertex-ai) (Gemini Pro Vision)
- **Maps**: [Google Maps API](https://developers.google.com/maps)
- **Server**: [Uvicorn](https://www.uvicorn.org/)

## Prerequisites

- Python 3.9+
- Google Cloud Platform Account (with Vertex AI enabled)
- Google Maps API Key

## Setup

1.  **Navigate to the project root** (where `requirements.txt` is located).

2.  **Create a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configuration:**
    Ensure you have your authentication credentials set up for Google Cloud (e.g., `GOOGLE_APPLICATION_CREDENTIALS` environment variable) and any necessary API keys.

## Running the Server

Run the server from the project root directory:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## API Endpoints

### Forensic Audit
`POST /audit/forensic`
- Upload multiple documents (PDF, Images).
- Returns analysis findings and status.

### Geospatial Audit
`POST /audit/geospatial`
- Inputs: `lat`, `lng`, `image` (site photo).
- Returns verification result (`SAFE`, `RISK`, `UNCERTAIN`) and analysis details.

### Health Check
`GET /`
- Returns status of the API.

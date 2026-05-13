# TitleTrust: Gemini 3 Hackathon Technical Analysis

## Part 1: Auto-Detected Tech Stack & Frameworks

### Core Frameworks
*   **Mobile Frontend:** **Flutter** (Dart 3.2+)
*   **Backend API:** **FastAPI** (Python 3.10+) based on `backend/routers` and `main.py`.

### Libraries & Dependencies
*   **State Management:** `flutter_riverpod` (Riverpod 2.5.1) with `riverpod_annotation`.
*   **Networking:** `dio` (Frontend), `uvicorn` / `fastapi` (Backend).
*   **Data & Auth:** `firebase_auth`, `cloud_firestore` (Frontend & Backend), `pydantic` (Backend Data Validation).
*   **Hardware/Sensors:** `camera`, `geolocator`, `google_maps_flutter` (Frontend).
*   **Maps/Location:** `googlemaps` (Python client for Backend verification).

### Current AI/ML Components
*   **SDK:** **Unified Google GenAI SDK** (`google-genai`) found in `backend/agent/`.
*   **Models:**
    *   `gemini-3-pro-preview`: Used for "Forensic Audit" reasoning and complex analysis (`audit.py`, `marathon.py`).
    *   `gemini-3-flash-preview`: Used for "Vision" tasks and "Titbits" generation (`vision.py`, `audit.py`).
*   **Advanced Features:**
    *   **Thinking Config:** Enabled in `LandAuditAgent` (`include_thoughts=True`).
    *   **Context Caching:** Implemented in `context_loader.py` for "Legal Knowledge Base".
    *   **Structured Outputs:** Used in `vision.py` (`DeedSchema`) and `titbits` endpoint.

---

## Part 2: Architecture & User Flow

### 1. System Architecture
The system follows a **Cloud-Native Hybrid Architecture**:
*   **Client (Flutter):** Acts as the "Sensor Array". It handles data capture (Camera/GPS), user authentication (Firebase), and displays real-time state. All heavy logic is offloaded.
*   **API Layer (FastAPI):** Acts as the "Orchestrator". It receives raw data, authenticates requests via Firebase Admin, and routes tasks to specific AI Agents.
*   **Agentic Layer (Gemini 3):**
    *   **Forensic Engine:** `forensic_engine.py` digests PDFs/Images using specific prompts.
    *   **Geospatial Engine:** `geospatial_engine.py` synchronizes Satellite data with User Ground Photos.
    *   **Marathon Service:** A background worker (`BackgroundTasks`) that runs the long-lived `LandAuditAgent`.
*   **Data Persistence:** Firestore is used for storing "Sessions" and "Audit Reports", allowing the frontend to subscribe to updates (e.g., "Processing" -> "Flagged").

### 2. Key Features List
*   **Forensic Document Audit:** Upload "Deal Packs" (Title Deeds, Sale Agreements) to detect fraud indicators.
*   **Live Geospatial Verification:** "Prove you are there." Captures Lat/Long + Photo and verifies consistency using Gemini Vision.
*   **Marathon Investigation:** A "Deep Dive" mode where an agent runs a multi-step investigation (Search Web + Legal Checks).
*   **Legal Knowledge Base:** Uses Gemini's `cached_content` to ground answers in the "Kenyan Land Act" and Constitution.
*   **Titbits:** Generates educational snippets about land law during loading screens.

### 3. User Flow (Reverse-Engineered)
1.  **Entry:** User logs in (Email/Google) -> lands on **Dashboard**.
2.  **Action:** User clicks **"New Investigation"**.
3.  **Selection:** User chooses **"Forensic Audit"** (Document Scan) or **"Site Visit"** (Geospatial).
    *   *Path A (Forensic):* User selects images/PDFs -> Uploads -> Backend processes (async) -> User sees "Analyzing...".
    *   *Path B (Site Visit):* User stands on land -> App captures GPS -> User takes Photo -> Backend compares GPS-Map vs Photo -> Returns "Verified/Fake".
4.  **Result:** Backend updates Firestore -> Frontend updates UI with **Risk Score (0-100)** and **Critical Findings**.
5.  **Review:** User taps finding to see "Evidence" (e.g., "Clause X of Land Act violated").

---

## Part 3: Gemini 3 Integration Strategy (The Winning Pivot)

To maximize scores in "Innovation" and "Technical Execution", integrate these specific Gemini 3 capabilities:

### 1. Multimodality: "The Virtual Surveyor" (Video)
*   **Current:** Single image upload for site verification.
*   **The Pivot:** **Video Walkthrough Analysis.**
    *   *Implementation:* Allow user to record a 15s video walking the property boundary.
    *   *Tech:* Send video to **Gemini 3 Pro Vision**. Ask it to "Identify boundary markers (beacons), neighboring structures, and any signs of dispute (e.g., broken fences, 'Use Warning' signs)."
    *   *Why:* Proves "Active Possession" better than a photo. Detecting a "Warning: Trespassers will be prosecuted" sign in a video frame is a huge fraud signal.

### 2. Deep Thinking: "The Constitutional Lawyer"
*   **Current:** Standard prompt reasoning.
*   **The Pivot:** **Conflict of Laws Resolution.**
    *   *Implementation:* When a "Title Deed" (Land Act) conflicts with a "Zoning Map" (County Gov Act), use **Gemini 3 Thinking Mode** (`include_thoughts=True`).
    *   *Prompt:* "Reason through the hierarchy of laws. Does the National Land Act capability override the County Zoning in this specific context? Show your chain of thought."
    *   *Why:* Demonstrates the model's ability to handle *nuance* and *ambiguity*, which is exactly what the "Thinking" mode is built for.

### 3. Agentic Capabilities: "The Autonomous Registry Clerk"
*   **Current:** Static knowledge base (cached PDFs).
*   **The Pivot:** **Active Evidence Gathering Agent.**
    *   *Implementation:* Upgrade `LandAuditAgent` in `marathon.py` with restartable logic.
    *   *Tool:* Give it a "Search Tool" (Google Search Grounding) to look for the specific "Title Number" in recent *Kenya Gazette* notices (which publish lost/stolen titles).
    *   *Flow:* Agent sees Title `IR 12345` -> Agent *decides* to search "Kenya Gazette IR 12345 lost title" -> Agent finds a match -> Agent *decides* to flag as "High Risk".
    *   *Why:* Moves from "Passive Analysis" (reading what I gave you) to "Active Investigation" (finding what I didn't give you).

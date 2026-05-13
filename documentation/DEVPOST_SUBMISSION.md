# TitleTrust: The Autonomous Land Due Diligence Agent
**"In God We Trust, In Land We Verify."**

## The Inspiration: Stopping the "Air Supply"
In Kenya, and across the Global South, land fraud is an epidemic. Innocent buyers lose life savings to "Air Supply"—land that doesn't exist, is double-sold, or is owned by the government. The problem isn't a lack of data; it's that the data is fragmented across dusty registries, complex legal statutes, and the physical ground itself.

We asked: **What if you had a Senior Forensic Auditor, a Constitutional Lawyer, and a Surveyor in your pocket, working 24/7?**

TitleTrust is the answer. It is not just a database wrapper; it is an **Autonomous Agent** powered by Gemini 3 that "thinks," "sees," and "verifies" reality against the record.

## What It Does
TitleTrust replaces the expensive, opaque 30-day due diligence process with a 3-minute AI audit. It works through three specialized AI agents:

1.  **The Digital Lawyer (Deep Thinking):** It doesn't just read documents; it *reasons* through them. It checks if a Title Deed's "Grant Number" matches the historical timeline of the Land Act, spotting forgeries that look perfect to the naked eye.
2.  **The Omniscient Surveyor (Multimodal Live Vision):** Users stand on the land and stream video. The agent identifies boundary beacons, neighbor encroachments, and "Warning" signs in real-time, cross-referencing GPS data with satellite imagery to prove "Active Possession."
3.  **The Forensic Auditor (Agentic Search):** A background agent that tirelessly scours the "Kenya Gazette" and online legal notices for mention of the specific Title Number in previous fraud cases or "Lost Title" claims.

## How We Built It
We built a clean, cloud-native hybrid architecture to ensure reliability in low-bandwidth execution environments:

*   **Frontend:** **Flutter (Dart)** for a high-performance, cross-platform mobile experience that handles the device sensors (Camera, GPS).
*   **Backend:** **FastAPI (Python)** acting as the central neural orchestration layer.
*   **Orchestration:** **Firebase** for real-time state syncing between the AI agents and the mobile user.

### Visible "Thought Signatures"
TitleTrust is not a black box. We implemented **Visible Thought Signatures** using Gemini 3. Every action taken by the backend is preceded by a structured reasoning step stored in Firestore. The agent self-reflects: if a government portal is down, it writes a log entry *"Portal unresponsive, thinking... I will sleep for 30 mins and retry,"* proving autonomous resilience in the face of failure.

### Serverless "Wake-Up" Mechanism
Unlike standard chatbots that die when the tab closes, TitleTrust utilizes a serverless **Heartbeat** via Cloud Tasks. The agent creates its own cron jobs dynamically based on the task difficulty. If an audit requires 24 hours, the agent schedules itself to wake up, check status, and notify the user via FCM, truly defining the **Action Era** of "Fire-and-Forget" applications.

## The Gemini 3.0 Advantage
We didn't just use Gemini 3 as a chatbot; we leveraged its native cognitive architecture to solve problems that were previously impossible for AI:

### 1. "Deep Thinking" for Legal Reasoning
Legal due diligence is not about retrieval; it's about **conflict resolution**.
*   *Challenge:* A County Zoning map might say "Residential," but the National Land Act says "Riparian Reserve."
*   *Gemini Solution:* We use **Gemini 3 Pro's "Thinking" mode** (`include_thoughts=True`). It parses the hierarchy of laws, explicitly reasoning that "National Law overrides County Law," and flags the land as high-risk. Standard LLMs would just hallucinate a compromise; Gemini 3 *judges*.

### 2. Multimodal Live API for Zero-Trust Verification
Photos can be old. Metadata can be spoofed.
*   *Challenge:* Proving a user is physically present on the land *right now*.
*   *Gemini Solution:* We utilized the **Gemini 3 Multimodal Live API**. The user scans the environment, and the model verbally confirms, *"I see the boundary beacon to your left, but it appears shifted compared to the satellite map."* This low-latency, real-time visual reasoning is the game-changer for remote verification.

## Challenges & Accomplishments
*   **Prompting "Abductive Reasoning":** Getting an AI to think like a detective (looking for what is *missing*) was hard. We successfully engineered "Thinking" prompts that force the model to identify negative evidence (e.g., "The lack of a stamp on this page is suspicious").
*   **Live API Latency:** Streaming video from rural Kenya to the Gemini API required aggressive optimization of our WebSocket frame handling, but seeing the AI recognize a specific type of "Concrete Beacon" in real-time was a magic moment.

## What's Next for TitleTrust
*   Integration with blockchain-based Land Registries.
*   Expansion of the "Knowledge Base" to include Case Law from the Environment and Land Court.

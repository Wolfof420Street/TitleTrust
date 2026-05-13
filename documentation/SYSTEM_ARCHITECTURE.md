# TitleTrust System Architecture

This is the architecture that emerges from the code, not a marketing diagram.

## High-Level Component Map

```mermaid
flowchart LR
    subgraph Mobile[Flutter Mobile App]
        M1[Auth / Login]
        M2[Forensic Screen]
        M3[Geospatial Screen]
        M4[Marathon Start]
        M5[Live Investigation UI]
        M6[Secure Storage + Request Signing]
    end

    subgraph API[FastAPI Backend]
        A1[main.py middleware stack]
        A2[auth_router]
        A3[audit_router]
        A4[authorization + policy]
        A5[session_service]
        A6[background_job_service]
        A7[audit_service]
    end

    subgraph Runtime[Async Runtime]
        R1[Redis Queue]
        R2[Cloud Tasks]
        R3[Worker Runtime]
    end

    subgraph Data[Persistence]
        D1[(Firestore sessions)]
        D2[(Firestore jobs)]
        D3[(Firestore device_sessions)]
        D4[(Firestore audit_events)]
        D5[(Firestore policies/memberships)]
        D6[(Redis rate limit store)]
    end

    subgraph Cloud[External Services]
        C1[Firebase Auth]
        C2[Gemini / GenAI]
        C3[Google Maps]
        C4[Firebase Messaging]
        C5[OTLP / Jaeger]
    end

    M1 --> C1
    M1 --> M6
    M2 --> A3
    M3 --> A3
    M4 --> A3
    M5 --> D1
    M6 --> A2

    A1 --> A2
    A1 --> A3
    A1 --> C5
    A2 --> D3
    A2 --> D5
    A3 --> A5
    A3 --> A6
    A7 --> C2

    A6 --> R1
    A6 --> R3
    R2 --> A3
    R3 --> C2
    R3 --> D2
    R3 --> D4

    A5 --> D1
    A5 --> D4
    A5 --> R2
    A4 --> D5
    A4 --> D1
    A4 --> D3
    C4 --> M5
```

## Runtime Layers

### Client layer
The Flutter app is not a thin demo shell. It includes:
- auth and biometric gating
- local secure storage
- request signing and correlation headers
- file uploads and camera/location capture
- Firestore stream consumption for live investigation state

### API layer
The FastAPI backend owns:
- token verification
- request-signing verification
- policy and permission enforcement
- file validation
- session/job persistence
- dispatch to background work

### Worker layer
The worker owns:
- long-running forensic analysis
- geospatial model invocation
- retries and backoff
- dead-letter routing
- heartbeat and queue-depth metrics

### Data layer
Firestore is the system of record for:
- sessions
- jobs
- audit trails
- device sessions
- policy/membership state

Redis is used for:
- distributed queueing
- rate limiting
- worker cancellation markers
- heartbeats and queue depth observation

## Auth Lifecycle Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant F as Flutter App
    participant FB as Firebase Auth
    participant B as FastAPI
    participant FS as Firestore

    U->>F: Sign in with Google
    F->>FB: Firebase sign-in
    FB-->>F: ID token
    F->>F: Generate device secret + session id
    F->>B: POST /auth/device-sessions
    B->>B: Verify Firebase token
    B->>B: Verify request signature
    B->>FS: Store encrypted device session
    B-->>F: registered
```

What is notable here:
- authentication and transport integrity are separate concerns
- the device session binds the app install to future requests
- backend authorization still applies after auth succeeds

## Request Lifecycle Diagram

```mermaid
sequenceDiagram
    participant F as Flutter Dio
    participant M as Middleware
    participant P as Permission/Auth
    participant S as Service
    participant D as Firestore

    F->>M: HTTP request with auth + signature
    M->>M: security headers, abuse score, correlation id
    M->>P: bearer auth + permission gate
    P->>P: Firebase verification + policy evaluation
    P->>S: route handler
    S->>D: repository writes/reads
    D-->>S: state
    S-->>M: response
    M-->>F: response + trace headers
```

## Queue Lifecycle Diagram

```mermaid
flowchart TD
    Q1[POST /audit/forensic or /audit/geospatial] --> Q2[BackgroundJobService validates upload]
    Q2 --> Q3[Create Firestore job document]
    Q3 --> Q4{QUEUE_MODE == redis?}
    Q4 -->|yes| Q5[Redis enqueue]
    Q4 -->|no| Q6[BackgroundTasks / inline worker call]
    Q5 --> Q7[WorkerRuntime polls queue]
    Q6 --> Q7
    Q7 --> Q8{job ok?}
    Q8 -->|yes| Q9[Update job completed]
    Q8 -->|no| Q10[retry / defer / dead-letter]
```

Key design point:
- queueing is a runtime choice, not a hardcoded single path. The code supports local development without Redis while preserving the same job semantics.

## Investigation Lifecycle

```mermaid
flowchart LR
    A[Start marathon] --> B[Create session doc]
    B --> C[Bootstrap first step]
    C --> D{Agent running?}
    D -->|yes| E[Schedule Cloud Task tick]
    D -->|no| F[Terminal state]
    E --> G[Tick endpoint]
    G --> H[run_single_step]
    H --> I{Running again?}
    I -->|yes| E
    I -->|no| F
```

Important behavior:
- state is persisted in Firestore so the agent can be resumed after process restarts
- Cloud Tasks is only the scheduler; the actual reasoning state lives in the session document

## Telemetry Lifecycle

```mermaid
flowchart LR
    R[Request] --> C[CorrelationMiddleware]
    C --> O[OpenTelemetry span]
    C --> H[HTTP counters/latency]
    C --> A[Adaptive abuse counters/scores]
    C --> L[Structured logs]
    F[Flutter app] --> X[Crashlytics/Sentry]
```

Why this architecture matters:
- it keeps the correlation id visible across client, API, and worker surfaces
- it gives operations a consistent handle to trace a single incident
- it allows the backend to run without telemetry exporters configured, which is useful for development and failure recovery

## What Is Interesting About This Architecture

This is a hybrid of:
- mobile-first UX
- trust-boundary-heavy API design
- workflow orchestration with persisted state
- AI-in-the-loop investigation
- observability-first runtime hygiene

The engineering value is not the UI chrome. It is the fact that the codebase explicitly models:
- request integrity
- job lifecycle
- policy evaluation
- audit trails
- worker resilience
- abuse detection
- partial degradation in local and cloud environments

That is the actual system shape.

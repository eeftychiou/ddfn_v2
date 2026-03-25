# Phase 10: Third-Party "Observer" APIs (The B2B Gateway)

## 1. Architectural Objective
Eurocontrol NM's B2B (Business-to-Business) web services provide the backbone for the entire European aviation software ecosystem (e.g., LIDO flight planning, ForeFlight, airport stand management systems). 

These third-party vendors need access to systemic capacity, slot assignments, and flight plans. However, granting them direct WebSocket access to the DDFN SWIM mesh is an extreme security risk (as they could accidentally publish negotiation payloads). We must build a read-only, air-gapped gateway layer mimicking the legacy B2B REST/SOAP APIs.

## 2. Core Principles
*   **Air-Gapped Pub/Sub**: External APIs never touch the core WebSocket mesh directly.
*   **Backward Compatibility**: Structuring gateway responses to loosely mimic legacy B2B structures to ease airline transition.
*   **Rate Limiting**: Protecting the core mesh from external DDOS via the gateway abstraction.

## 3. Implementation Plan

### 3.1. The Edge Gateway Service
1.  **Passive Subscriber Node**: Create a new service (`gateway_service.py`) that acts as a passive consumer on the core Broker. It subscribes to `#.*` but is cryptographically barred (Phase 5) from publishing anything.
2.  **In-Memory Materialized Views**: The gateway continuously parses the SWIM firehose into high-speed Redis maps representing the *current* state of the entire network (Global FDPS, Global Sector Capacities).

### 3.2. Public REST / GraphQL API
1.  **Endpoints**: Expose standardized REST endpoints via FastAPI:
    - `GET /api/v1/flights/{flight_id}` -> Returns current 4D trajectory and assigned CTOT.
    - `GET /api/v1/airspace/{fir_id}/capacity` -> Returns current RED/GREEN status and hourly AAR.
2.  **Authentication & Throttling**: Implement OAuth2 API keys specifically for B2B consumers, using `slowapi` or similar middleware to enforce strict rate limiting.

## 4. Expected Outcomes
*   A robust method for the legacy aviation ecosystem to extract real-time situational awareness from the decentralized swarm without compromising its security or peer-to-peer latency.

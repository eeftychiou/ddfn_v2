# DDFN v2 Operational & Deployment Roadmap

Building the algorithmic logic and rigorously testing it is only half the battle. To successfully replace Eurocontrol NM, DDFN must operate as a highly observable, legally compliant, and safely deployable enterprise system. 

This roadmap covers "Day-2" operations: Observability, Data Archiving, Regulatory Compliance, and the strategic rollout plan.

---

## Phase 8: Distributed Tracing & Observability
**Goal:** In a decentralized mesh, debugging a dropped message or a delayed CTOT assignment is impossible using traditional logs. DDFN requires enterprise-grade distributed tracing.
- **OpenTelemetry Integration**: Instrument `fastapi`, `websockets`, and `pydantic` parsers across all nodes to inject W3C Trace Context headers into every SWIM payload.
- **Jaeger/Zipkin Dashboards**: Deploy a central tracing UI allowing operators to search a specific `flight_id` and visualize exactly which FMPs ray-casted it, which Airport ran an auction for it, and where the consensus was finalized, down to the millisecond.
- **Alerting Rules**: Expand the current Prometheus `/metrics` to trigger PagerDuty/Slack alerts when end-to-end `FLIGHT_PLAN_FILED` processing latency exceeds 500ms.

## Phase 9: Big Data Archiving (The Data Lake)
**Goal:** Eurocontrol NM processes enormous amounts of historical data for post-operations analysis, delay attribution, and airline billing. The current local SQLite database (`audit.db`) is insufficient for a continent's worth of traffic.
- **SWIM Firehose to Cloud Storage**: Construct a dedicated "Archiver Node" that passively subscribes to `#.*` (all topics) on the Broker and streams the JSON payloads into an Apache Kafka cluster or AWS S3 Data Lake (using Parquet formatting).
- **Post-Ops Machine Learning**: Enable offline analytics teams to query the Data Lake via AWS Athena/Snowflake to train predictive Machine Learning models on sector capacity degradation, feeding those models back into the FMP's D-1 strategic simulations (Phase 7).

## Phase 10: Human-Machine Interface (HMI) Safety & UX
**Goal:** The current React dashboards are functional prototypes. Managing 10,000+ flights safely requires heavily vetted, aviation-grade UX.
- **Macro-Situational Awareness**: FMP operators need a cross-FIR dashboard that visualizes not just their own sectors, but the impending "Ripple" coming from adjacent distressed sectors before the alarms trigger.
- **HMI Safety Audits**: Conduct eye-tracking and cognitive-load studies on the UI. Ensure that when a `UI_INBOX_APPROVAL_REQUEST` (HITL request) pops up during high-stress periods, the consequence of "Approve" vs "Reject" is unambiguously clear to the Flow Controller.

## Phase 11: Regulatory Certification & Compliance
**Goal:** Aviation software cannot be deployed into live airspace management without strict regulatory sign-offs from EASA and ICAO.
- **DO-278AL / ED-109A Alignment**: Formally document the Software Assurance Level (SWAL) of the DDFN components. 
- **Safety Case Generation**: Produce the required Hazard Analysis and Risk Assessment (HARA) documents proving that a catastrophic failure of the Broker or an FMP node will unequivocally fail-safe without causing mid-air conflicts (since ATFM is a strategic separator, not a tactical ATC separator, the AL-level is lower, but still requires immense documentation).

## Phase 12: Shadow Operations & Cutover Strategy
**Goal:** You cannot physically shut off Eurocontrol NM and turn on DDFN overnight. There must be a phased, risk-free transition period.
- **Live B2B Ingestion Layer**: Build an ingestor that connects to Eurocontrol's live B2B (Business-to-Business) web services. It pulls live `FPL`, `DLA`, `CHG`, and `SAM` messages and converts them into DDFN `FLIGHT_PLAN_FILED` SWIM formats.
- **Shadow Mode**: DDFN runs entirely in the background using live European traffic data. Distributed CASA acts on the traffic, but the resulting `DISTRIBUTED_FLOW_CONSENSUS` CTOTs are merely logged, *never* sent back to the aircraft.
- **CTOT Delta Analysis**: Analytics teams compare the CTOTs assigned by the legacy Eurocontrol NM CASA against the localized CTOTs assigned by DDFN's Ripple algorithm. Once airlines and regulators are confident that the DDFN CTOTs are as efficient (and more resilient) than the legacy system, the formal regulatory cutover can happen.

## Phase 13: Distributed Route Charges & Settlement (The CRCO Equivalent)
**Goal:** Eurocontrol's Central Route Charges Office (CRCO) bills airlines on behalf of Air Navigation Service Providers (ANSPs) based on weight formulas and distance flown. Relinquishing a central database means DDFN must provide a decentralized, trustless billing settlement layer.
- **Smart Contract / Distributed Ledger Billing**: Transition CRCO logic into isolated, automated smart contracts. When a flight physically transits an FMP's Area of Responsibility, the `FIR_HANDOVER_ADVISORY` acts as a cryptographic proof-of-transit.
- **Automated Settlement**: The proof is appended to a shared ledger (established in Phase 5/6), automatically calculating the unit rate and aircraft weight factor.
- **Decentralized Clearinghouse**: Airlines (AOCs) settle their aggregate route charges periodically via the shared ledger directly with the respective ANSPs, replacing the centralized CRCO invoicing bottleneck with automated, verifiable peer-to-peer micro-accounting.

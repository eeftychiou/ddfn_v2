# DDFN V2 — Agentic Coding Guide

This document provides context and guidelines for AI agents (e.g., Antigravity) working on the DDFN v2 codebase. It captures architectural decisions, security principles, and development patterns established during the v2 audit and hardening effort.

> [!IMPORTANT]
> This file should be updated whenever significant architectural, security, or reliability changes are made to the system.

---

## 1. Project Context

**DDFN v2** (Decentralized Demand & Capacity Balancing) is a peer-to-peer ATFM (Air Traffic Flow Management) system that replaces centralized flow management (like Eurocontrol NM) with a decentralized SWIM messaging network.

### Key Design Constraints
- **No global state**: Every node manages only its local FIR sectors.
- **Eventual consistency**: Consensus is achieved via message passing, not shared memory.
- **Determinism**: All nodes must produce identical outcomes given identical message sequences.
- **Resilience**: Nodes must survive network partitions, restarts, and duplicate messages.

---

## 2. Architecture Quick Reference

### Node Types
| Node | File | Role |
|------|------|------|
| Broker | `core/broker.py` | Passive WebSocket message router + audit logger |
| FMP | `services/fmp_service.py` | Regional Flow Management Position (demand/capacity analysis, CASA) |
| Airport | `services/airport_service.py` | Local FDPS (AAR/ADR monitoring, GDP triggers, clearinghouse) |
| AOC | `services/aoc_service.py` | Airline Operations Center (fleet management, REA broadcasts) |
| Sim Manager | `services/sim_manager.py` | Simulation control panel (flight injection, AIXM loading) |

### Core Data Flow
```
FMP Node → detects capacity breach
    → emits CONSTRAINT_WARNING_TRIGGER
    → runs CASA algorithm → generates CTOT slots
    → emits CTOT_ASSIGNMENT_PROPOSAL
    → participating nodes vote
    → consensus reached → emit DISTRIBUTED_FLOW_CONSENSUS
    → all nodes apply CTOTs to local FDPS
```

---

## 3. Critical Implementation Rules

### 3.1 Async-First I/O
All database and network I/O must be non-blocking:
- Use `aiosqlite` for SQLite (not `sqlite3`)
- Use `aiofiles` for file operations
- The `PersistenceManager` and `NetworkClient` must never block the event loop

### 3.2 Idempotency
Every message handler must be idempotent:
- Check `persistence.is_processed(message_id)` before acting
- Mark processed with `persistence.mark_processed(message_id)` after acting
- This applies to: proposals, consensus messages, overrides, and RAD updates

### 3.3 CTOT Calculation (CASA Algorithm)
The CASA slot allocation algorithm assigns CTOTs based on the **assigned slot time**, not `departure_time + delay`:

```python
# CORRECT
delay = int((assigned_slot - eto).total_seconds() / 60)
ctot = assigned_slot.isoformat()

# WRONG — breaks for in-flight aircraft
ctot = (flt.departure_time + timedelta(minutes=delay)).isoformat()
```

### 3.4 Input Sanitization
All user uploads must be sanitized:
- Strip path components from filenames (`os.path.basename`)
- Use UUID-based storage names
- Validate file extensions against a whitelist
- Enforce maximum file sizes (e.g., 100MB for AIXM)

### 3.5 Secret Management
- API keys must **never** be logged to stdout/stderr
- Auto-generated keys emit a generic warning without revealing the value
- Use `logging.getLogger("auth").warning(...)` not `print(...)`

---

## 4. Testing Guidelines

### Required Test Coverage
When modifying any of these components, add/update tests:
- **CASA logic**: `tests/unit/test_regulation_service.py`
- **Persistence**: `tests/unit/test_persistence.py` (async pytest)
- **Models**: `tests/unit/test_models.py`
- **AIXM parsing**: `tests/unit/test_aixm_tool.py`

### Running Tests
```bash
# Full suite (excluding pre-existing failures)
python -m pytest tests/unit/ --ignore=tests/unit/test_broker_unit.py --ignore=tests/unit/test_rad_unit.py

# Specific component
python -m pytest tests/unit/test_regulation_service.py -v
```

### Pre-Existing Known Failures
Do not attempt to fix these unless explicitly requested:
- `test_broker_subscribe` — broker unit test (WebSocket timing issue)
- `test_rad_lf_003_special_logic` — RAD validator edge case

---

## 5. Logging Standards

Use structured logging, never `print()`:
- Module-level loggers: `logger = logging.getLogger("module_name")`
- Log levels:
  - `DEBUG`: Detailed flow tracing (e.g., "_parse_route checking token=X")
  - `INFO`: Significant state changes (e.g., "CASA calculated N delayed flights")
  - `WARNING`: Recoverable issues (e.g., "Connection lost, retrying...")
  - `ERROR`: Failures requiring attention (e.g., "Failed to save override")

---

## 6. Common Pitfalls

| Pitfall | Location | Prevention |
|---------|----------|------------|
| Blocking SQLite in async handler | `persistence.py` | Use `aiosqlite` with WAL mode |
| Synchronous file I/O in async context | `fmp_service.py` | Use `aiofiles` |
| Path traversal in file uploads | `fmp_service.py` | Sanitize + UUID filenames |
| CTOT recalculation from departure_time | `regulation_service.py` | Use `assigned_slot` directly |
| Messages lost during disconnect | `network.py` | Use outbound message buffer |
| Fixed sleep reconnection | `network.py` | Use exponential backoff + jitter |
| Duplicate message processing | All handlers | Check `is_processed()` first |

---

## 7. Dependencies

Core dependencies:
- `fastapi`, `uvicorn` — HTTP/WebSocket server
- `websockets` — WebSocket client
- `aiosqlite` — Async SQLite
- `aiofiles` — Async file I/O
- `pydantic` — Data validation

Add new dependencies only when necessary. Prefer standard library alternatives.

---

## 8. Documentation Updates

When making changes, update:
1. **`Architecture.md`** — For component relationship, data flow, or design principle changes
2. **`README.md`** — For user-facing changes (APIs, configuration, setup)
3. **`agents.md`** — For patterns, pitfalls, or agent-relevant architectural decisions

---

## 9. Change Log (Agent-Relevant)

| Date | Change | Files |
|------|--------|-------|
| 2026-05-04 | Fixed path traversal in AIXM upload | `fmp_service.py` |
| 2026-05-04 | Fixed CTOT calculation bug | `regulation_service.py` |
| 2026-05-04 | Replaced all print() with logging | `trajectories.py`, `airspace.py`, `fmp_service.py`, `rad_validator.py`, `schedule.py`, `auth.py` |
| 2026-05-04 | Migrated to async SQLite | `persistence.py`, `fmp_service.py`, `test_persistence.py` |
| 2026-05-04 | Added message buffering + exponential backoff | `network.py` |
| 2026-05-04 | Added CASA unit tests | `test_regulation_service.py` |

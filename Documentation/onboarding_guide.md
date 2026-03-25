# DDFN v2 Developer Onboarding Guide

Welcome to the **Decentralized Demand & Capacity Balancing (DDFN) prototype v2**. 

If you are coming from traditional web development or legacy ATFM (Air Traffic Flow Management) systems, the architecture of this project will feel radically different. **You are not building a centralized REST API.** You are building a "swarm" of independent actors that negotiate purely through an event-driven publish/subscribe network.

This guide will help you shift your mindset and navigate the codebase safely.

---

## 1. The Core Paradigm: Think Like a Swarm

In legacy aviation systems, there is usually a "God Node" (like the Eurocontrol Network Manager) that stores all flight plans, calculates all delays, and dictates all slots.

**In DDFN v2, the central authority does not exist.**

- The central Broker (`broker.py`) is completely stateless. It does not know what a "flight" or a "sector" is. It blindly routes JSON payloads. **NEVER add business logic or state constraints to the broker.**
- Every node (`fmp_service.py`, `airport_service.py`, `aoc_service.py`) boots up completely blind.
- Each node builds its own partial worldview by independently listening to flight plans and calculating trajectories locally.

If a single FMP node crashes, the rest of the European airspace mesh will continue balancing its local queues unimpeded. This is the ultimate goal of the project.

---

## 2. Navigating the Codebase

### A. The Networking & Data Contract
Because there are no direct REST API calls between nodes, the **JSON schemas are the absolute source of truth**. If you change a message structure, you risk breaking the entire mesh in ways that are hard to debug (split-brain).
- 📍 **Look at:** `src/ddfn_v2/core/models.py`. This contains the Pydantic v2 schemas for every single object in the network.
- 📖 **Read:** The [Protocol Message Dictionary](protocol_message_dictionary.md) to understand who sends what topic and why.

### B. The Nodes (The Swarm Actors)
- 📍 **`fmp_service.py`**: Regional area control. It manages complex geometries (AIXM sectors). It runs continuous background loops (`_sync_capacity()`) to predict demand mathematically and emits CASA delay proposals.
- 📍 **`airport_service.py`**: The endpoint nodes. They manage Arrival/Departure Rates and act as clearinghouses (running internal auctions) to resolve upstream flow constraints.
- 📖 **Read:** The [Node State-Machines](node_state_machines.md) to visualize how these algorithms sequence internally before reaching consensus.

### C. The Physics/Geometry Engine
Nodes do not rely on standard mock "Estimated Times of Arrival" strings. 
- 📍 **Look at:** `src/ddfn_v2/eng/trajectories.py`. 
When a flight plan is filed, this engine uses geodesic math (Haversine), atmospheric True Airspeed models, and ray-casting point-in-polygon (`_point_in_polygon`) to figure out exactly when a vector intersects a geographical sector. 

---

## 3. Development Golden Rules

As you implement new features, adhere to these strictly:

1. **Beware the Infinite Loop**: In a dense pub/sub mesh, an unhandled message rebroadcast will cause an infinite loop. Always use persistence checks (e.g., `processed_proposal_ids` or `processed_consensus_ids`) before acting on a network message.
2. **Lock Mutable State**: Since nodes run fully asynchronous loops (receiving network traffic, computing CASA, recalculating trajectories simultaneously), always use `asyncio.Lock()` (`self._state_lock`) when modifying the internal `FlightDataProcessingSystem` (FDPS) or constraint lists.
3. **No Central API Polling**: If a node needs data from another node (e.g. knowing if an airline is ready to fly), it must wait for that node to publish it over SWIM. Do not add HTTP `GET` requests between microservices! 

---

## 4. Next Steps

1. Launch the local cluster using `./start_demo.ps1` (or `docker-compose up` if configured).
2. Open the Broker UI (`http://127.0.0.1:8001`) to watch the raw SWIM mesh activity.
3. Open an FMP Dashboard (e.g., `http://127.0.0.1:8010`) to see the localized worldview rendered dynamically from the raw network traffic.

Happy coding! If you adhere to the decentralized contracts, you are building the future of peer-to-peer airspace management.

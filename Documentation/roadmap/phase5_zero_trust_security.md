# Phase 5: Zero-Trust Security & Cryptographic Trajectories

## 1. Architectural Objective
Legacy systems like Eurocontrol NM operate within heavily isolated intranets with a central trusted authority (IFPS). Consequently, internal messages are implicitly trusted.

DDFN_v2 is a decentralized publisher/subscriber mesh. Currently, any node can publish a `DISTRIBUTED_FLOW_CONSENSUS` allocating a prime slot to their own flights. To become a viable rival, DDFN must transition to a **Zero-Trust Architecture** where every trajectory constraint, slot swap, and delay proposal is mathematically verified to prevent malicious airline or node spoofing.

## 2. Core Principles
*   **Cryptographic Sovereignty**: "Code is Law." A slot (CTOT) cannot be stolen if the cryptographic signature of the controlling FMP or clearinghouse does not match.
*   **Immutable Pub/Sub**: The Broker rejects unauthorized payloads purely through middleware header evaluation, keeping the core message router ultra-fast and stateless.
*   **Decentralized Key Management**: PKI operates via a distributed registry rather than a single CA (Certificate Authority).

## 3. Implementation Plan

### 3.1. Node PKI Infrastructure (`core/security.py`)
1.  **Key Pair Generation**: Upon first boot, every node (FMP, Airport, AOC, SimManager) generates an **Ed25519** asymmetric key pair.
2.  **Registration Pipeline**: Nodes submit an `INIT_NODE_REGISTRATION` payload to the network containing their Public Key. A distributed registry database (or a smart contract logic overlay) stores the `node_id` <-> `public_key` mapping.

### 3.2. Payload Signing Configuration (`core/models.py`)
1.  **BaseModel Inheritance**: Modify the underlying Pydantic Base model for all SWIM messages:
```python
class SecureSwimMessage(BaseModel):
    message_type: str
    timestamp: datetime
    node_id: str
    payload_hash: str     # SHA-256 of the JSON body
    signature: str        # Ed25519 signature of the hash
```
2.  **Automated Signing Middleware**: Intercept all outbound `websockets.send()` commands in `network.py` and transparently inject the cryptographic signature using the node's private key.

### 3.3. Broker Verification Middleware (`core/broker.py`)
1.  **Signature Verification**: The Broker reads the `node_id` and looks up the associated public key in the shared registry.
2.  **Hash Verification**: It re-calculates the SHA-256 hash of the incoming JSON body. If it deviates from `payload_hash`, the message was tampered with in transit.
3.  **Rejection Policy**: Any mismatch results in immediate WebSocket termination (`CloseCode 1008: Policy Violation`) and a persistent log in the `audit.db` identifying the spoofing attempt by IP/Node.

### 3.4. Multi-Signature Consensus
1.  **Slot Swapping Protection**: An AOC emitting `FMP_SLOT_SWAP_REQUEST` must have its payload validated not just by the Broker, but the receiving Airport Node must verify the AOC's signature before allowing the flight to jump the CASA queue.

## 4. Expected Outcomes
*   A cryptographically secure ATFM mesh immune to state manipulation, spoofing, and unauthorized slot reallocation.
*   Lays the fundamental groundwork for integrating blockchain ledgers into global airspace management logs.

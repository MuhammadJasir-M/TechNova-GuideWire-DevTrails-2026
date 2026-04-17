# GuideWire-DevTrials Real-Time Mock Data Implementation Plan

## Objective

Transform GuideWire-DevTrials into a real-time, event-driven experience similar to the Neonatal Monitoring System by integrating:

- Continuous mock data simulation
- Live dashboard updates
- Event streaming (WebSocket/SSE)
- End-to-end scenario orchestration (trigger -> claim -> investigation -> payout)

## Scope

- Reuse existing mock APIs:
  - `mock-apis/weather_api.py`
  - `mock-apis/imd_api.py`
  - `mock-apis/aqicn_api.py`
  - `mock-apis/zomato_api.py`
  - `mock-apis/razorpay_api.py`
- Add backend event simulator and broadcaster
- Add frontend real-time state and live UI components
- Add test coverage for scenarios and streaming

## Current Gaps vs Neonatal-Style Liveliness

- Dashboard refresh is mostly request-driven
- No continuous event feed for workers/admins
- Alerts are not fully real-time pushed
- Charts/cards are mostly static after initial fetch

## Target Experience

- New synthetic events every 15-30 seconds
- Dashboard cards and charts auto-update every 2-5 seconds
- Worker and admin activity feed updates instantly
- Critical alerts appear as live notifications
- Claims pipeline visible end-to-end in real time

---

## Architecture Overview

### Backend Additions

1. **MockDataSimulator**
   - Rotates through realistic insurance scenarios
   - Calls existing mock APIs to generate signals
   - Creates triggers/claims/payout events

2. **EventBroadcaster**
   - In-memory event queue (bounded)
   - Broadcasts to worker/admin channels
   - Supports replay of recent events for reconnect

3. **Streaming Layer**
   - WebSocket endpoints for real-time clients
   - SSE fallback endpoint for constrained environments

4. **Scheduler Integration**
   - Runs scenarios on interval
   - Controlled by env flags

### Frontend Additions

1. `useWebSocket` hook with reconnect/backoff
2. `RealtimeContext` for shared live state
3. Activity feed component for event timeline
4. Dashboard upgrades for live cards/charts/alerts
5. Admin dashboard live queue + risk/fraud stream

---

## Implementation Phases

## Phase 1 - Backend Mock Data Foundation (4-6 hours)

### Deliverables

- `backend/services/mock_data_simulator.py`
- `backend/services/event_broadcaster.py`
- Baseline event schema and queue

### Work Items

- Define rotating scenario templates:
  - Heavy Rain Event
  - Heat + AQI Event
  - Fraud Ring Pattern
  - New Worker Lifecycle
  - Normal Operations
- Implement scenario runner:
  - Gather external signals from mock APIs
  - Generate trigger records
  - Create and update claim lifecycle states
  - Emit standardized events
- Add bounded queue and event deduping keys where needed

### Outcome

System can continuously generate realistic, business-aligned synthetic events.

---

## Phase 2 - Real-Time Streaming Backend (3-4 hours)

### Deliverables

- `backend/api/websocket.py`
- Streaming routes in backend app

### Work Items

- Add WebSocket endpoints:
  - `/ws/events` (worker-scoped)
  - `/ws/admin` (global admin stream)
- Add SSE endpoint:
  - `/api/events/sse`
- JWT-authenticate streaming connections
- Room/topic routing:
  - worker-specific
  - admin-global
  - zone-specific (optional)
- Add reconnect replay from last N events

### Outcome

Clients can subscribe and receive near real-time events without polling.

---

## Phase 3 - Frontend Live Dashboard Upgrade (5-7 hours)

### Deliverables

- `frontend/src/hooks/useWebSocket.ts`
- `frontend/src/context/RealtimeContext.tsx`
- `frontend/src/components/ActivityFeed.tsx`
- Worker/Admin dashboard real-time wiring

### Work Items

- Build reusable `useWebSocket` hook with:
  - auto reconnect
  - exponential backoff
  - connection state
  - event filtering
- Add `RealtimeContext` for:
  - recent events
  - active triggers
  - latest claims snapshots
  - connection health
- Update Worker dashboard:
  - live zone alert banner
  - live policy/claim status
  - live earnings protected card
- Update Admin dashboard:
  - live claims queue
  - investigation progress stream
  - fraud alert panel
- Add subtle transitions/animations for incoming updates

### Outcome

UI behaves as a live operations console rather than a static report view.

---

## Phase 4 - Scenario Orchestration and Fidelity (4-5 hours)

### Deliverables

- `backend/services/scenario_templates.py`
- `backend/services/scenario_executor.py`

### Work Items

- Encode timing-based scenario steps (T+0, T+5, T+15...)
- Add realistic randomness:
  - rainfall and temperature ranges
  - worker participation rates
  - claim approval variance by trust score
  - payout processing delay windows
- Include multi-signal validation logic where possible

### Outcome

Scenarios look realistic in demos and exercise core business paths consistently.

---

## Phase 5 - Integration, Testing, and Ops Controls (4-6 hours)

### Deliverables

- Backend tests for simulator/streaming
- Frontend e2e tests for live updates
- Environment toggles and run instructions

### Work Items

- Backend tests:
  - scenario execution
  - event queue behavior
  - websocket broadcasting
- Frontend e2e:
  - stream connect/reconnect
  - dashboard updates on events
  - activity feed rendering
- Add env flags:
  - `ENABLE_MOCK_SCENARIOS=true`
  - `MOCK_SCENARIO_INTERVAL=15`
  - `WEBSOCKET_ENABLED=true`
  - `MOCK_EVENT_QUEUE_SIZE=1000`
- Add docs update and troubleshooting checklist

### Outcome

Feature is stable, configurable, and demo-ready.

---

## Recommended Event Types

- `TRIGGER_DETECTED`
- `ZONE_ALERT`
- `CLAIM_AUTO_FILED`
- `INVESTIGATION_STARTED`
- `INVESTIGATION_COMPLETED`
- `CLAIM_APPROVED`
- `CLAIM_REJECTED`
- `PAYOUT_INITIATED`
- `PAYOUT_COMPLETED`
- `FRAUD_RING_DETECTED`

## Event Payload (Suggested)

```json
{
  "event_id": "evt_123",
  "event_type": "CLAIM_APPROVED",
  "timestamp": "2026-04-17T10:35:00Z",
  "priority": "HIGH",
  "worker_id": "wrk_001",
  "zone_code": "CHN-VEL-4B",
  "data": {
    "claim_id": "clm_9182",
    "amount": 4200,
    "reason": "HEAVY_RAIN"
  }
}
```

---

## Data Seeding Strategy

1. Seed baseline entities from DB seed scripts (workers/zones/policies)
2. Run scenario simulator continuously to produce time-based live events
3. Persist selected outputs (claims/payouts/notifications) for dashboard history
4. Keep recent live event queue in memory for fast stream replay

## Why Existing Mock APIs Are Enough

Yes, the existing `mock-apis` can be applied directly:

- Weather + IMD + AQICN provide trigger signals
- Zomato provides worker/order operational context
- Razorpay simulates payout completion states
  This already covers the full parametric insurance chain for realistic simulation.

---

## Rollout Plan

1. Build backend simulator + broadcaster first
2. Enable streaming endpoints and test with CLI clients
3. Integrate frontend real-time context and dashboard widgets
4. Enable scenario rotation and tune timings
5. Add tests and ops toggles

## Acceptance Criteria

- Live events appear on dashboard within <= 3 seconds
- Worker and admin views both receive role-appropriate streams
- Claims lifecycle is visible end-to-end without manual refresh
- Mock mode can be toggled on/off via env config
- Existing REST behavior remains backward-compatible

## Estimated Total Effort

- **20-28 hours** for comprehensive implementation with testing

## Next Step (Execution Order)

1. Implement Phase 1 and Phase 2 in backend
2. Wire Phase 3 frontend live updates
3. Complete Phase 4 realism tuning
4. Finish Phase 5 testing and hardening

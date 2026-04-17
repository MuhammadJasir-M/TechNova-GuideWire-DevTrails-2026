"""
Tests for WebSocket and SSE streaming endpoints.
"""

import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock

from backend.services.event_broadcaster import EventBroadcaster, SimulatorEvent, get_broadcaster


# ──────────────────────────── WebSocket Integration Tests ────────

class TestWebSocketEndpoints:
    """Tests for the WebSocket endpoint module logic."""

    @pytest.mark.asyncio
    async def test_broadcaster_integration_with_ws(self):
        """Simulate what happens when a WS client subscribes and events are broadcast."""
        broadcaster = EventBroadcaster(max_replay=100)

        # Simulate worker subscription
        q_worker = await broadcaster.subscribe("worker:wrk_001")
        q_zone = await broadcaster.subscribe("zone:CHN-VEL-4B")
        q_admin = await broadcaster.subscribe("admin")

        # Simulate event broadcast
        event = SimulatorEvent.create(
            event_type="TRIGGER_DETECTED",
            priority="HIGH",
            zone_code="CHN-VEL-4B",
            data={"trigger_type": "HEAVY_RAIN", "rainfall_mm": 120},
            worker_id="wrk_001",
        )
        delivered = await broadcaster.broadcast(event)

        # Worker should get it (via worker channel)
        assert not q_worker.empty()
        # Zone channel should get it
        assert not q_zone.empty()
        # Admin should always get it
        assert not q_admin.empty()
        assert delivered >= 3

        # Cleanup
        await broadcaster.unsubscribe("worker:wrk_001", q_worker)
        await broadcaster.unsubscribe("zone:CHN-VEL-4B", q_zone)
        await broadcaster.unsubscribe("admin", q_admin)

    @pytest.mark.asyncio
    async def test_replay_on_subscribe(self):
        """Verify that new subscribers can get recent events."""
        broadcaster = EventBroadcaster(max_replay=100)

        # Generate some events before subscription
        for i in range(5):
            event = SimulatorEvent.create(
                event_type=f"EVENT_{i}",
                priority="MEDIUM",
                zone_code="CHN-VEL-4B",
            )
            await broadcaster.broadcast(event)

        # Now get replay
        recent = await broadcaster.get_recent(10)
        assert len(recent) == 5
        assert recent[0]["event_type"] == "EVENT_0"
        assert recent[4]["event_type"] == "EVENT_4"

    @pytest.mark.asyncio
    async def test_multiple_clients_same_channel(self):
        """Multiple WS clients on same channel all receive events."""
        broadcaster = EventBroadcaster(max_replay=50)

        clients = []
        for _ in range(5):
            q = await broadcaster.subscribe("admin")
            clients.append(q)

        event = SimulatorEvent.create("TEST", "LOW", "X")
        await broadcaster.broadcast(event)

        for q in clients:
            assert not q.empty()
            msg = q.get_nowait()
            assert msg["event_type"] == "TEST"

        for q in clients:
            await broadcaster.unsubscribe("admin", q)

    @pytest.mark.asyncio
    async def test_client_disconnect_cleanup(self):
        """After unsubscribe, client queue should no longer receive events."""
        broadcaster = EventBroadcaster(max_replay=50)
        q = await broadcaster.subscribe("admin")

        # Unsubscribe
        await broadcaster.unsubscribe("admin", q)

        # Broadcast after disconnect
        event = SimulatorEvent.create("POST_DISCONNECT", "LOW", "X")
        await broadcaster.broadcast(event)

        assert q.empty()

    @pytest.mark.asyncio
    async def test_concurrent_broadcasts(self):
        """Test that concurrent broadcasts don't corrupt state."""
        broadcaster = EventBroadcaster(max_replay=200)
        q = await broadcaster.subscribe("admin")

        # Broadcast 100 events concurrently
        events = [
            SimulatorEvent.create(f"CONCURRENT_{i}", "LOW", "X")
            for i in range(100)
        ]
        await asyncio.gather(
            *[broadcaster.broadcast(e) for e in events]
        )

        assert q.qsize() == 100
        assert broadcaster.event_count == 100

        await broadcaster.unsubscribe("admin", q)


# ──────────────────────────── SSE Tests ──────────────────────────

class TestSSELogic:
    """Test the SSE streaming logic (event serialization)."""

    def test_event_json_serializable(self):
        event = SimulatorEvent.create(
            event_type="PAYOUT_COMPLETED",
            priority="HIGH",
            zone_code="CHN-VEL-4B",
            data={"amount": 1200, "transaction_id": "UPI_123456"},
            worker_id="wrk_001",
        )
        payload = event.to_dict()
        # Should be JSON serializable
        json_str = json.dumps(payload)
        assert "PAYOUT_COMPLETED" in json_str

        # SSE format
        sse_data = f"data: {json_str}\n\n"
        assert sse_data.startswith("data: ")
        assert sse_data.endswith("\n\n")

    def test_all_event_types_serializable(self):
        event_types = [
            "TRIGGER_DETECTED", "ZONE_ALERT", "CLAIM_AUTO_FILED",
            "INVESTIGATION_STARTED", "INVESTIGATION_COMPLETED",
            "CLAIM_APPROVED", "CLAIM_REJECTED",
            "PAYOUT_INITIATED", "PAYOUT_COMPLETED",
            "FRAUD_RING_DETECTED",
        ]
        for et in event_types:
            event = SimulatorEvent.create(et, "MEDIUM", "CHN-VEL-4B")
            json.dumps(event.to_dict())  # Should not raise


# ──────────────────────────── Channel Routing Tests ───────────────

class TestChannelRouting:
    """Verify the channel routing logic matches what the WS handlers expect."""

    @pytest.mark.asyncio
    async def test_worker_receives_own_events(self):
        broadcaster = EventBroadcaster()
        q = await broadcaster.subscribe("worker:wrk_005")

        event = SimulatorEvent.create(
            "CLAIM_APPROVED", "HIGH", "CHN-VEL-4B",
            data={"amount": 500},
            worker_id="wrk_005",
        )
        await broadcaster.broadcast(event)

        assert not q.empty()
        await broadcaster.unsubscribe("worker:wrk_005", q)

    @pytest.mark.asyncio
    async def test_worker_does_not_receive_others(self):
        broadcaster = EventBroadcaster()
        q = await broadcaster.subscribe("worker:wrk_005")

        event = SimulatorEvent.create(
            "CLAIM_APPROVED", "HIGH", "CHN-VEL-4B",
            worker_id="wrk_010",
        )
        await broadcaster.broadcast(event)

        assert q.empty()
        await broadcaster.unsubscribe("worker:wrk_005", q)

    @pytest.mark.asyncio
    async def test_zone_subscription(self):
        broadcaster = EventBroadcaster()
        q = await broadcaster.subscribe("zone:MUM-AND-1A")

        event = SimulatorEvent.create(
            "ZONE_ALERT", "CRITICAL", "MUM-AND-1A",
            data={"message": "Flooding in Andheri"},
        )
        await broadcaster.broadcast(event)

        assert not q.empty()
        msg = q.get_nowait()
        assert msg["data"]["message"] == "Flooding in Andheri"

        await broadcaster.unsubscribe("zone:MUM-AND-1A", q)

    @pytest.mark.asyncio
    async def test_admin_receives_everything(self):
        broadcaster = EventBroadcaster()
        q = await broadcaster.subscribe("admin")

        # Events for different workers and zones
        for i in range(5):
            event = SimulatorEvent.create(
                "TEST", "LOW", f"ZONE_{i}",
                worker_id=f"wrk_{i:03d}",
            )
            await broadcaster.broadcast(event)

        assert q.qsize() == 5
        await broadcaster.unsubscribe("admin", q)

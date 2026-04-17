"""
Tests for the Mock Data Simulator and Event Broadcaster.
"""

import asyncio
import pytest
import pytest_asyncio

from backend.services.event_broadcaster import EventBroadcaster, SimulatorEvent, get_broadcaster
from backend.services.scenario_templates import (
    pick_scenario, ALL_SCENARIOS, ZONE_POOL, WORKER_POOL,
    ScenarioStep, ScenarioTemplate,
)
from backend.services.mock_data_simulator import MockDataSimulator


# ──────────────────────────── SimulatorEvent ─────────────────────

class TestSimulatorEvent:
    def test_create_event(self):
        event = SimulatorEvent.create(
            event_type="TRIGGER_DETECTED",
            priority="HIGH",
            zone_code="CHN-VEL-4B",
            data={"rainfall_mm": 120.5},
            worker_id="wrk_001",
        )
        assert event.event_id.startswith("evt_")
        assert event.event_type == "TRIGGER_DETECTED"
        assert event.priority == "HIGH"
        assert event.zone_code == "CHN-VEL-4B"
        assert event.data["rainfall_mm"] == 120.5
        assert event.worker_id == "wrk_001"
        assert event.source == "simulator"

    def test_to_dict(self):
        event = SimulatorEvent.create(
            event_type="CLAIM_APPROVED",
            priority="MEDIUM",
            zone_code="BLR-KOR-1A",
        )
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["event_type"] == "CLAIM_APPROVED"
        assert "event_id" in d
        assert "timestamp" in d

    def test_event_ids_unique(self):
        events = [
            SimulatorEvent.create("TEST", "LOW", "X") for _ in range(100)
        ]
        ids = {e.event_id for e in events}
        assert len(ids) == 100


# ──────────────────────────── EventBroadcaster ───────────────────

class TestEventBroadcaster:
    @pytest.fixture
    def broadcaster(self):
        return EventBroadcaster(max_replay=50)

    @pytest.mark.asyncio
    async def test_subscribe_and_broadcast(self, broadcaster):
        q = await broadcaster.subscribe("admin")
        event = SimulatorEvent.create("TEST", "LOW", "CHN-VEL-4B")
        delivered = await broadcaster.broadcast(event)
        assert delivered >= 1
        msg = q.get_nowait()
        assert msg["event_type"] == "TEST"

    @pytest.mark.asyncio
    async def test_channel_routing_worker(self, broadcaster):
        q_worker = await broadcaster.subscribe("worker:wrk_001")
        q_other = await broadcaster.subscribe("worker:wrk_002")

        event = SimulatorEvent.create(
            "CLAIM_APPROVED", "HIGH", "CHN-VEL-4B",
            worker_id="wrk_001"
        )
        await broadcaster.broadcast(event)

        assert not q_worker.empty()
        assert q_other.empty()

    @pytest.mark.asyncio
    async def test_channel_routing_zone(self, broadcaster):
        q_zone = await broadcaster.subscribe("zone:CHN-VEL-4B")
        q_other = await broadcaster.subscribe("zone:BLR-KOR-1A")

        event = SimulatorEvent.create(
            "ZONE_ALERT", "HIGH", "CHN-VEL-4B"
        )
        await broadcaster.broadcast(event)

        assert not q_zone.empty()
        assert q_other.empty()

    @pytest.mark.asyncio
    async def test_admin_gets_all(self, broadcaster):
        q_admin = await broadcaster.subscribe("admin")

        for zone in ["CHN-VEL-4B", "BLR-KOR-1A", "MUM-AND-1A"]:
            event = SimulatorEvent.create("TEST", "LOW", zone)
            await broadcaster.broadcast(event)

        assert q_admin.qsize() == 3

    @pytest.mark.asyncio
    async def test_replay_buffer(self, broadcaster):
        for i in range(10):
            event = SimulatorEvent.create("TEST", "LOW", f"ZONE_{i}")
            await broadcaster.broadcast(event)

        recent = await broadcaster.get_recent(5)
        assert len(recent) == 5
        # Most recent should be last
        assert recent[-1]["zone_code"] == "ZONE_9"

    @pytest.mark.asyncio
    async def test_replay_buffer_bounded(self, broadcaster):
        # Broadcaster has max_replay=50
        for i in range(100):
            event = SimulatorEvent.create("TEST", "LOW", f"Z_{i}")
            await broadcaster.broadcast(event)

        recent = await broadcaster.get_recent(100)
        assert len(recent) == 50  # bounded

    @pytest.mark.asyncio
    async def test_unsubscribe(self, broadcaster):
        q = await broadcaster.subscribe("admin")
        await broadcaster.unsubscribe("admin", q)

        event = SimulatorEvent.create("TEST", "LOW", "X")
        delivered = await broadcaster.broadcast(event)
        assert delivered == 0

    @pytest.mark.asyncio
    async def test_event_count(self, broadcaster):
        assert broadcaster.event_count == 0
        for _ in range(5):
            await broadcaster.broadcast(
                SimulatorEvent.create("TEST", "LOW", "X")
            )
        assert broadcaster.event_count == 5

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_channel(self, broadcaster):
        q1 = await broadcaster.subscribe("admin")
        q2 = await broadcaster.subscribe("admin")

        event = SimulatorEvent.create("TEST", "LOW", "X")
        delivered = await broadcaster.broadcast(event)

        assert delivered >= 2
        assert not q1.empty()
        assert not q2.empty()


# ──────────────────────────── Scenario Templates ─────────────────

class TestScenarioTemplates:
    def test_all_scenarios_exist(self):
        assert len(ALL_SCENARIOS) >= 5

    def test_all_scenarios_have_steps(self):
        for scenario in ALL_SCENARIOS:
            assert len(scenario.steps) > 0
            assert scenario.name
            assert scenario.description
            assert scenario.weight > 0

    def test_pick_scenario_returns_template(self):
        for _ in range(20):
            s = pick_scenario()
            assert isinstance(s, ScenarioTemplate)
            assert s.name in [t.name for t in ALL_SCENARIOS]

    def test_step_data_generation(self):
        for scenario in ALL_SCENARIOS:
            ctx = {}
            for step in scenario.steps:
                data = step.generate_data(ctx)
                assert isinstance(data, dict)

    def test_zone_pool_not_empty(self):
        assert len(ZONE_POOL) > 0
        for zone in ZONE_POOL:
            assert len(zone) == 3  # code, city, area

    def test_worker_pool_not_empty(self):
        assert len(WORKER_POOL) > 0


# ──────────────────────────── MockDataSimulator ──────────────────

class TestMockDataSimulator:
    def test_simulator_creation(self):
        sim = MockDataSimulator(interval=10)
        assert not sim.is_running
        assert sim.cycles_completed == 0

    @pytest.mark.asyncio
    async def test_emit_single(self):
        sim = MockDataSimulator(interval=60)
        broadcaster = get_broadcaster()
        q = await broadcaster.subscribe("admin")

        event = await sim.emit_single(
            event_type="TEST_SINGLE",
            priority="HIGH",
            zone_code="CHN-VEL-4B",
            data={"test": True},
        )

        assert event.event_type == "TEST_SINGLE"
        msg = q.get_nowait()
        assert msg["event_type"] == "TEST_SINGLE"
        assert msg["data"]["test"] is True

        await broadcaster.unsubscribe("admin", q)

    @pytest.mark.asyncio
    async def test_start_stop(self):
        sim = MockDataSimulator(interval=60)
        sim.start()
        assert sim.is_running

        # Let it run briefly
        await asyncio.sleep(0.1)

        sim.stop()
        assert not sim.is_running

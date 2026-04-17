"""
GigPulse Sentinel — Mock Data Simulator

Continuously generates realistic insurance-lifecycle events by cycling
through scenario templates.  Each cycle:

1.  Picks a weighted-random scenario template
2.  Walks through the template steps with realistic delays
3.  Calls existing mock-API functions for signal enrichment
4.  Broadcasts events via the EventBroadcaster

Controlled by environment flags:
    ENABLE_MOCK_SCENARIOS  = true | false
    MOCK_SCENARIO_INTERVAL = seconds between full scenario cycles
"""

from __future__ import annotations

import asyncio
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from backend.services.event_broadcaster import SimulatorEvent, get_broadcaster
from backend.services.scenario_templates import pick_scenario, ScenarioTemplate

logger = logging.getLogger("gigpulse.simulator")


# ───────────────── Mock-API helpers ─────────────────────────────────

def _ensure_mock_apis_importable() -> None:
    """Add the mock-apis directory to sys.path so we can call them."""
    mock_dir = str(Path(__file__).resolve().parent.parent.parent / "mock-apis")
    if mock_dir not in sys.path:
        sys.path.append(mock_dir)


async def _enrich_weather(zone_code: str, lat: float = 12.98, lon: float = 80.22) -> dict:
    """Call the mock weather API and return a summary dict."""
    _ensure_mock_apis_importable()
    try:
        from weather_api import get_current_weather
        data = await get_current_weather(lat=lat, lon=lon, zone_code=zone_code)
        return {
            "temp": data["main"]["temp"],
            "rainfall_mm": data.get("rain", {}).get("1h", 0) if data.get("rain") else 0,
            "humidity": data["main"]["humidity"],
            "condition": data["weather"][0]["main"],
        }
    except Exception as exc:
        logger.warning("Weather enrichment failed: %s", exc)
        return {}


async def _enrich_aqi(zone_code: str) -> dict:
    _ensure_mock_apis_importable()
    try:
        from aqicn_api import get_mock_aqi
        data = await get_mock_aqi(city="chennai", zone_code=zone_code)
        return {
            "aqi": data["data"]["aqi"],
            "category": data["data"]["category"],
            "pollutant": data["data"]["dominant_pollutant"],
        }
    except Exception as exc:
        logger.warning("AQI enrichment failed: %s", exc)
        return {}


async def _enrich_platform(zone_code: str) -> dict:
    _ensure_mock_apis_importable()
    try:
        from zomato_api import get_zone_status
        data = await get_zone_status(zone_code=zone_code)
        return {
            "active_riders": data.get("active_riders", 0),
            "pending_orders": data.get("pending_orders", 0),
            "zone_status": data.get("status", "ACTIVE"),
        }
    except Exception as exc:
        logger.warning("Platform enrichment failed: %s", exc)
        return {}


# ───────────────── Simulator ────────────────────────────────────────

class MockDataSimulator:
    """Runs continuous scenario loops in the background."""

    def __init__(self, interval: int = 20) -> None:
        self._interval = interval
        self._broadcaster = get_broadcaster()
        self._running = False
        self._task: asyncio.Task | None = None
        self._cycles_completed = 0

    # -- lifecycle ----------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "MockDataSimulator started (interval=%ds)", self._interval
        )

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("MockDataSimulator stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycles_completed(self) -> int:
        return self._cycles_completed

    # -- core loop ----------------------------------------------------

    async def _run_loop(self) -> None:
        """Main loop: pick scenario → execute steps → wait → repeat."""
        # Small initial delay so the app finishes startup first
        await asyncio.sleep(2)

        while self._running:
            try:
                scenario = pick_scenario()
                logger.info("▶ Scenario: %s", scenario.name)
                await self._execute_scenario(scenario)
                self._cycles_completed += 1
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scenario execution error")

            # Wait before next cycle (with jitter)
            jitter = random.uniform(-3, 5)
            await asyncio.sleep(max(5, self._interval + jitter))

    async def _execute_scenario(self, scenario: ScenarioTemplate) -> None:
        """Walk through scenario steps, emitting events."""
        ctx: dict = {}  # shared mutable context across steps
        prev_delay = 0

        for step in scenario.steps:
            if not self._running:
                break

            # Wait the relative delay between steps
            wait = max(0, step.delay_seconds - prev_delay)
            if wait > 0:
                await asyncio.sleep(wait)
            prev_delay = step.delay_seconds

            # Generate event data from the step
            step_data = step.generate_data(ctx)

            # Enrich with mock-API signals for trigger events
            zone_code = step_data.get("zone_code") or ctx.get("zone", ("",))[0]
            if step.event_type in ("TRIGGER_DETECTED", "ZONE_ALERT") and zone_code:
                weather = await _enrich_weather(zone_code)
                aqi = await _enrich_aqi(zone_code)
                platform = await _enrich_platform(zone_code)
                step_data["signals"] = {
                    "weather": weather,
                    "aqi": aqi,
                    "platform": platform,
                }

            # Build and broadcast
            event = SimulatorEvent.create(
                event_type=step.event_type,
                priority=step.priority,
                zone_code=zone_code,
                data=step_data,
                worker_id=step_data.get("worker_id") or ctx.get("worker"),
            )

            await self._broadcaster.broadcast(event)
            logger.debug(
                "  ⤷ %s [%s] zone=%s",
                event.event_type,
                event.priority,
                event.zone_code,
            )

    # -- manual trigger (useful for testing) --------------------------

    async def emit_single(self, event_type: str, priority: str,
                          zone_code: str, data: dict | None = None,
                          worker_id: str | None = None) -> SimulatorEvent:
        """Emit a one-off event outside the scenario loop."""
        event = SimulatorEvent.create(
            event_type=event_type,
            priority=priority,
            zone_code=zone_code,
            data=data,
            worker_id=worker_id,
        )
        await self._broadcaster.broadcast(event)
        return event


# ───────────────── Module-level singleton ───────────────────────────

_simulator: MockDataSimulator | None = None


def get_simulator(interval: int = 20) -> MockDataSimulator:
    global _simulator
    if _simulator is None:
        _simulator = MockDataSimulator(interval=interval)
    return _simulator

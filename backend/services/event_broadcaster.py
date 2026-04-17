"""
GigPulse Sentinel — Event Broadcaster

In-memory pub/sub hub that routes simulator events to WebSocket/SSE
subscribers.  Maintains a bounded replay buffer so reconnecting clients
can catch up on missed events.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
import uuid

logger = logging.getLogger("gigpulse.broadcaster")


# ───────────────────────── Event Dataclass ──────────────────────────

@dataclass
class SimulatorEvent:
    """Canonical event emitted by the mock-data simulator."""

    event_id: str
    event_type: str
    timestamp: str
    priority: str          # LOW | MEDIUM | HIGH | CRITICAL
    zone_code: str
    data: dict = field(default_factory=dict)
    worker_id: str | None = None
    source: str = "simulator"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def create(
        event_type: str,
        priority: str,
        zone_code: str,
        data: dict | None = None,
        worker_id: str | None = None,
    ) -> "SimulatorEvent":
        return SimulatorEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            priority=priority,
            zone_code=zone_code,
            data=data or {},
            worker_id=worker_id,
        )


# ───────────────────────── Broadcaster ──────────────────────────────

class EventBroadcaster:
    """Singleton-style in-memory event fan-out.

    Channels
    --------
    * ``admin``          – receives every event
    * ``worker:{id}``    – events scoped to a specific worker
    * ``zone:{code}``    – events for a specific zone
    """

    def __init__(self, max_replay: int = 1000) -> None:
        self._lock = asyncio.Lock()
        # channel → set of asyncio.Queue
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        # bounded ring-buffer for replay
        self._replay_buffer: deque[dict] = deque(maxlen=max_replay)
        self._event_count = 0

    # ---- public API ---------------------------------------------------

    async def broadcast(self, event: SimulatorEvent) -> int:
        """Push *event* to every matching channel.

        Returns the number of subscribers that received it.
        """
        payload = event.to_dict()
        delivered = 0

        async with self._lock:
            self._replay_buffer.append(payload)
            self._event_count += 1

            # Determine target channels
            channels: list[str] = ["admin"]  # admin always gets everything
            if event.zone_code:
                channels.append(f"zone:{event.zone_code}")
            if event.worker_id:
                channels.append(f"worker:{event.worker_id}")

            for ch in channels:
                for q in self._subscribers.get(ch, set()):
                    try:
                        q.put_nowait(payload)
                        delivered += 1
                    except asyncio.QueueFull:
                        # Drop oldest to make room (back-pressure)
                        try:
                            q.get_nowait()
                            q.put_nowait(payload)
                            delivered += 1
                        except Exception:
                            pass

        if delivered:
            logger.debug(
                "Broadcast %s to %d subscriber(s)", event.event_type, delivered
            )
        return delivered

    async def subscribe(self, channel: str, maxsize: int = 256) -> asyncio.Queue:
        """Create a new subscription queue for *channel*."""
        q: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        async with self._lock:
            self._subscribers.setdefault(channel, set()).add(q)
        logger.info("New subscriber on channel=%s (total=%d)", channel,
                     len(self._subscribers.get(channel, [])))
        return q

    async def unsubscribe(self, channel: str, q: asyncio.Queue) -> None:
        """Remove a subscription queue."""
        async with self._lock:
            subs = self._subscribers.get(channel)
            if subs:
                subs.discard(q)
                if not subs:
                    del self._subscribers[channel]
        logger.info("Unsubscribed from channel=%s", channel)

    async def get_recent(self, n: int = 50) -> list[dict]:
        """Return the last *n* events from the replay buffer."""
        async with self._lock:
            items = list(self._replay_buffer)
        return items[-n:]

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def subscriber_count(self) -> int:
        return sum(len(s) for s in self._subscribers.values())


# ───────────────────────── Module-level singleton ───────────────────

_broadcaster: EventBroadcaster | None = None


def get_broadcaster(max_replay: int = 1000) -> EventBroadcaster:
    """Return (or create) the global EventBroadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster(max_replay=max_replay)
    return _broadcaster

"""
GigPulse Sentinel — WebSocket & SSE Streaming Endpoints

Provides real-time event delivery to frontend clients:

    /ws/events   — worker-scoped WebSocket stream
    /ws/admin    — admin global WebSocket stream
    /api/events/sse — SSE fallback for constrained environments

All endpoints authenticate via JWT token passed as query parameter.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import StreamingResponse

from backend.config.settings import get_settings
from backend.services.event_broadcaster import get_broadcaster

logger = logging.getLogger("gigpulse.websocket")

router = APIRouter(tags=["Streaming"])
settings = get_settings()


# ───────────────── JWT helpers ──────────────────────────────────────

def _decode_token(token: str) -> dict | None:
    """Decode a JWT token and return payload, or None on failure."""
    try:
        from jose import jwt as jose_jwt
        payload = jose_jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except Exception:
        return None


# ───────────────── WebSocket: Worker events ─────────────────────────

@router.websocket("/ws/events")
async def ws_worker_events(websocket: WebSocket, token: str = Query(default="")):
    """Worker-scoped real-time event stream.

    Subscribes to:
      - worker:{worker_id}
      - zone:{zone_code}   (if available)
    """
    # Authenticate
    payload = _decode_token(token) if token else None
    if not payload:
        await websocket.close(code=4001, reason="Authentication required")
        return

    worker_id = payload.get("sub") or payload.get("worker_id")
    zone_code = payload.get("zone_code", "")
    role = payload.get("role", "WORKER")

    await websocket.accept()
    logger.info("WS connected: worker=%s zone=%s", worker_id, zone_code)

    broadcaster = get_broadcaster()

    # Send replay burst
    try:
        recent = await broadcaster.get_recent(30)
        # Filter to worker-relevant events
        for evt in recent:
            if (evt.get("worker_id") == worker_id or
                    evt.get("zone_code") == zone_code or
                    evt.get("priority") in ("HIGH", "CRITICAL")):
                await websocket.send_json(evt)
    except Exception as exc:
        logger.warning("Replay failed: %s", exc)

    # Subscribe to channels
    channels_queues: list[tuple[str, asyncio.Queue]] = []

    if worker_id:
        q = await broadcaster.subscribe(f"worker:{worker_id}")
        channels_queues.append((f"worker:{worker_id}", q))
    if zone_code:
        q = await broadcaster.subscribe(f"zone:{zone_code}")
        channels_queues.append((f"zone:{zone_code}", q))
    # Workers also get admin-level HIGH/CRITICAL events
    q_admin = await broadcaster.subscribe("admin")
    channels_queues.append(("admin", q_admin))

    try:
        while True:
            # Listen on all queues concurrently
            tasks = [
                asyncio.create_task(q.get()) for _, q in channels_queues
            ]
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            for p in pending:
                p.cancel()

            for task in done:
                try:
                    event = task.result()
                    # For worker-scoped, filter admin events to HIGH/CRITICAL
                    if event.get("priority") in ("HIGH", "CRITICAL") or \
                       event.get("worker_id") == worker_id or \
                       event.get("zone_code") == zone_code:
                        await websocket.send_json(event)
                except Exception:
                    pass

    except WebSocketDisconnect:
        logger.info("WS disconnected: worker=%s", worker_id)
    except Exception as exc:
        logger.warning("WS error: %s", exc)
    finally:
        for ch, q in channels_queues:
            await broadcaster.unsubscribe(ch, q)


# ───────────────── WebSocket: Admin stream ──────────────────────────

@router.websocket("/ws/admin")
async def ws_admin_stream(websocket: WebSocket, token: str = Query(default="")):
    """Admin global event stream — receives ALL events."""
    payload = _decode_token(token) if token else None
    if not payload:
        await websocket.close(code=4001, reason="Authentication required")
        return

    role = payload.get("role", "")
    if role not in ("ADMIN", "SUPER_ADMIN"):
        await websocket.close(code=4003, reason="Admin access required")
        return

    await websocket.accept()
    logger.info("WS admin connected: role=%s", role)

    broadcaster = get_broadcaster()

    # Send replay burst (all events)
    try:
        recent = await broadcaster.get_recent(50)
        for evt in recent:
            await websocket.send_json(evt)
    except Exception:
        pass

    # Subscribe to admin channel (gets everything)
    q = await broadcaster.subscribe("admin")

    try:
        while True:
            event = await q.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("WS admin disconnected")
    except Exception as exc:
        logger.warning("WS admin error: %s", exc)
    finally:
        await broadcaster.unsubscribe("admin", q)


# ───────────────── SSE fallback ─────────────────────────────────────

@router.get("/api/events/sse")
async def sse_event_stream(token: str = Query(default="")):
    """Server-Sent Events fallback for real-time event streaming."""
    payload = _decode_token(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="Authentication required")

    worker_id = payload.get("sub") or payload.get("worker_id")
    role = payload.get("role", "WORKER")
    is_admin = role in ("ADMIN", "SUPER_ADMIN")
    zone_code = payload.get("zone_code", "")

    broadcaster = get_broadcaster()

    async def event_generator():
        # Subscribe
        channel = "admin" if is_admin else (f"worker:{worker_id}" if worker_id else "admin")
        q = await broadcaster.subscribe(channel)

        try:
            # Replay burst
            recent = await broadcaster.get_recent(20)
            for evt in recent:
                yield f"data: {json.dumps(evt)}\n\n"

            # Stream live events
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield f": keepalive {datetime.now(timezone.utc).isoformat()}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await broadcaster.unsubscribe(channel, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ───────────────── Status endpoint ──────────────────────────────────

@router.get("/api/events/status")
async def events_status():
    """Public status endpoint for the event streaming system."""
    broadcaster = get_broadcaster()
    from backend.services.mock_data_simulator import get_simulator
    simulator = get_simulator()

    return {
        "streaming_enabled": settings.websocket_enabled,
        "simulator_running": simulator.is_running,
        "cycles_completed": simulator.cycles_completed,
        "total_events_broadcast": broadcaster.event_count,
        "active_subscribers": broadcaster.subscriber_count,
        "replay_buffer_size": len(broadcaster._replay_buffer),
    }
